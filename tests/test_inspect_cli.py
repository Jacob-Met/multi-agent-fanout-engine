"""Receive the existing-ledger inspection command through real SQLite files."""
from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import Ledger, Part, Plan, canonical_json, inspect_project


ROOT = Path(__file__).resolve().parents[1]


class InspectCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        punctuation = "#&=%" if os.name == "nt" else "#?&=%"
        self.database = self.root / f"ledger {punctuation} café.sqlite3"
        self.plan = Plan("retained", (
            Part("complete", "Accepted source.", tags=("source", "source")),
            Part("running", "Work still in progress."),
            Part("unknown", "Acceptance needs evidence."),
            Part("failed", "Evidence confirms failure."),
            Part("dispatching", "Local acknowledgement is incomplete."),
            Part("ready", "Use the accepted source.", depends_on=("complete",)),
            Part("blocked", "Wait for verified evidence.", depends_on=("unknown", "running")),
        ))
        route = {"model": "local-example", "effort": "low"}
        evidence = {"source": "local fixture", "locator": "fixture:receipt", "finding": "authored evidence"}
        with Ledger(str(self.database)) as ledger:
            ledger.record_plan(self.plan)
            for part_id in ("complete", "running", "unknown", "failed", "dispatching"):
                ledger.mark_dispatching("retained", part_id, "local-worker", route)
            for part_id in ("complete", "running"):
                ledger.mark_running("retained", part_id, "task-" + part_id)
            ledger.mark_completed("retained", "complete", "artifact:accepted", evidence)
            for part_id in ("unknown", "failed"):
                ledger.mark_outcome_unknown("retained", part_id, evidence)
            ledger.reconcile_unknown("retained", "failed", verdict="failed", evidence=evidence)
            self.expected = canonical_json(inspect_project(ledger, "retained")) + "\n"

    def run_cli(self, *args: str, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "fanout_engine.inspect", *args],
            cwd=ROOT, text=True, encoding="utf-8", capture_output=True,
            timeout=10, **kwargs,
        )

    def test_disk_report_matches_native_api_and_preserves_database(self) -> None:
        before = self.database.read_bytes()
        metadata = self.database.stat()
        siblings = sorted(path.name for path in self.root.iterdir())
        result = self.run_cli("--database", str(self.database), "--project", "retained")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.stdout, self.expected)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(self.database.stat().st_mtime_ns, metadata.st_mtime_ns)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), siblings)
        with Ledger(str(self.database)) as ledger:
            self.assertEqual(ledger.part_state("retained", "dispatching"), "dispatching")
            self.assertEqual(ledger.part_state("retained", "unknown"), "outcome_unknown")

    def test_readonly_constructor_reads_but_refuses_mutation(self) -> None:
        before = self.database.read_bytes()
        with Ledger.open_readonly(self.database) as ledger:
            self.assertEqual(canonical_json(inspect_project(ledger, "retained")) + "\n", self.expected)
            with self.assertRaises(sqlite3.OperationalError):
                ledger.mark_dispatching("retained", "ready", "worker", {"model": "m", "effort": "low"})
            self.assertEqual(ledger.part_state("retained", "ready"), "queued")
        self.assertEqual(self.database.read_bytes(), before)

    def test_readonly_constructor_does_not_initialize_schema(self) -> None:
        database = self.root / "unrelated.sqlite3"
        with closing(sqlite3.connect(database)) as connection, connection:
            connection.execute("CREATE TABLE preserved(value TEXT)")
            connection.execute("INSERT INTO preserved VALUES ('keep')")
        before = database.read_bytes()
        with Ledger.open_readonly(database) as ledger:
            with self.assertRaises(sqlite3.OperationalError):
                ledger.project_snapshot("retained")
        with closing(sqlite3.connect(database)) as connection, connection:
            tables = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            self.assertEqual(tables, [("preserved",)])
        self.assertEqual(database.read_bytes(), before)

    def test_missing_database_and_parent_are_not_created(self) -> None:
        for database in (self.root / "missing.sqlite3", self.root / "missing-parent" / "ledger.sqlite3"):
            with self.subTest(database=database):
                result = self.run_cli("--database", str(database), "--project", "retained")
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("cannot read ledger", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertFalse(database.exists())
        self.assertFalse((self.root / "missing-parent").exists())

    def test_unknown_project_is_distinct_and_has_no_success_output(self) -> None:
        before = self.database.read_bytes()
        result = self.run_cli("--database", str(self.database), "--project", "absent")
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "fanout inspect: project_not_found: project is not in the ledger\n")
        self.assertEqual(self.database.read_bytes(), before)

    def test_corrupt_empty_and_foreign_databases_are_not_repaired(self) -> None:
        foreign = self.root / "foreign.sqlite3"
        with closing(sqlite3.connect(foreign)) as connection, connection:
            connection.execute("CREATE TABLE keep(value TEXT)")
        empty = self.root / "empty.sqlite3"
        empty.touch()
        corrupt = self.root / "corrupt.sqlite3"
        corrupt.write_bytes(b"this is not a SQLite database\n")
        for database in (foreign, empty, corrupt):
            with self.subTest(database=database):
                before = database.read_bytes()
                result = self.run_cli("--database", str(database), "--project", "retained")
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("cannot read ledger", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertEqual(database.read_bytes(), before)

    def test_inconsistent_late_record_refuses_complete_report(self) -> None:
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE parts SET evidence_json='nullx' WHERE part_id='blocked'")
        before = self.database.read_bytes()
        result = self.run_cli("--database", str(self.database), "--project", "retained")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("invalid_record", result.stderr)
        self.assertEqual(self.database.read_bytes(), before)

    def test_missing_part_rows_are_reported_without_partial_output(self) -> None:
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("DELETE FROM parts WHERE part_id='blocked'")
        before = self.database.read_bytes()
        result = self.run_cli("--database", str(self.database), "--project", "retained")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("missing_parts", result.stderr)
        self.assertEqual(self.database.read_bytes(), before)

    def test_live_wal_reads_committed_state_and_ignores_uncommitted_changes(self) -> None:
        connection = sqlite3.connect(self.database, isolation_level=None)
        self.addCleanup(connection.close)
        self.assertEqual(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        connection.execute("UPDATE parts SET updated_at=1234.5 WHERE part_id='running'")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE parts SET updated_at=9876.5 WHERE part_id='running'")
        before = self.database.read_bytes()
        wal = Path(str(self.database) + "-wal")
        wal_before = wal.read_bytes()
        result = self.run_cli("--database", str(self.database), "--project", "retained")
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        report = json.loads(result.stdout)
        running = next(part for part in report["parts"] if part["id"] == "running")
        self.assertEqual(running["updated_at"], 1234.5)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(wal.read_bytes(), wal_before)
        self.assertTrue(connection.in_transaction)
        connection.rollback()

    def test_directory_and_fifo_inputs_refuse_without_blocking(self) -> None:
        inputs = [self.root]
        if hasattr(os, "mkfifo"):
            fifo = self.root / "ledger.pipe"
            os.mkfifo(fifo)
            inputs.append(fifo)
        for path in inputs:
            with self.subTest(path=path):
                result = self.run_cli("--database", str(path), "--project", "retained")
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("regular file", result.stderr)

    def test_relative_path_and_symlink_keep_selected_file_identity(self) -> None:
        relative = os.path.relpath(self.database, ROOT)
        result = self.run_cli("--database", relative, "--project", "retained")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.expected)
        link = self.root / "alias.sqlite3"
        try:
            link.symlink_to(self.database.name)
        except (OSError, NotImplementedError):
            return
        result = self.run_cli("--database", str(link), "--project", "retained")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, self.expected)
        self.assertTrue(link.is_symlink())

    @unittest.skipUnless(Path("/dev/full").exists(), "requires /dev/full")
    def test_output_write_failure_is_nonzero_without_shutdown_traceback(self) -> None:
        before = self.database.read_bytes()
        with open("/dev/full", "wb") as output:
            result = subprocess.run(
                [sys.executable, "-m", "fanout_engine.inspect", "--database", str(self.database), "--project", "retained"],
                cwd=ROOT, stdout=output, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", timeout=10,
            )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("cannot write report", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("Exception ignored", result.stderr)
        self.assertEqual(self.database.read_bytes(), before)

    def test_unknown_cli_option_refuses_before_opening_database(self) -> None:
        missing = self.root / "never-created.sqlite3"
        result = self.run_cli("--database", str(missing), "--project", "retained", "--write")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("unrecognized arguments", result.stderr)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
