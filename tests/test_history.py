from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import Ledger, Part, Plan
from fanout_engine.history import inspect_history
from fanout_engine.inspection import InspectionError
from fanout_engine.plan import canonical_json


ROOT = Path(__file__).resolve().parents[1]


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / "retained history.sqlite3"
        self.plan = Plan("sample", (
            Part("work", "Produce résumé", tags=("note", "note")),
            Part("review", "Review", depends_on=("work",)),
            Part("pending", "Still queued"),
            Part("interrupted", "No acceptance recorded"),
        ))
        with Ledger(str(self.database)) as ledger:
            ledger.record_plan(self.plan)
            route = {"model": "local-fixture", "effort": "high"}
            ledger.mark_dispatching("sample", "work", "fixture-worker", route)
            ledger.mark_running("sample", "work", "fixture-task")
            ledger.mark_completed("sample", "work", "fixture://résumé", {
                "source": "fixture", "locator": "fixture://work", "finding": "authored complete",
            })
            # Sequence IDs are global: another project's event creates a gap.
            ledger.record_plan(Plan("neighbor", (Part("other", "Other project"),)))
            ledger.mark_dispatching("sample", "review", "fixture-reviewer", route)
            ledger.mark_running("sample", "review", "fixture-review")
            ledger.mark_outcome_unknown("sample", "review", {
                "source": "fixture", "locator": "fixture://review", "finding": "unknown acceptance",
            })
            ledger.reconcile_unknown("sample", "review", verdict="failed", evidence={
                "source": "fixture", "locator": "fixture://finding", "finding": "authored failure",
            })
            ledger.mark_dispatching("sample", "interrupted", "fixture-worker", route)
            ledger.mark_interrupted_dispatches_unknown("sample")
            # Recorded order must not be inferred by sorting wall-clock times.
            ledger._db.execute("UPDATE events SET at=-seq")
            self.expected_events = ledger.events("sample")

    def cli(self, *arguments, stdout=subprocess.PIPE):
        return subprocess.run(
            [sys.executable, "-m", "fanout_engine.history", "--database", str(self.database),
             "--project", "sample", *arguments],
            cwd=ROOT, stdout=stdout, stderr=subprocess.PIPE, timeout=10,
        )

    def test_api_preserves_native_record_order_fields_and_details(self):
        with Ledger.open_readonly(self.database) as ledger:
            report = inspect_history(ledger, "sample")
            self.assertEqual(report, {
                "schema_version": 1, "project_id": "sample", "plan_digest": self.plan.digest,
                "part_id": None, "events": self.expected_events,
            })
            self.assertEqual([event["seq"] for event in report["events"]],
                             [1, 2, 3, 4, 6, 7, 8, 9, 10, 11])
            self.assertEqual(report["events"][0]["event"], "plan_recorded")
            self.assertEqual(report["events"][-1]["event"], "outcome_unknown")
            self.assertEqual(ledger._db.total_changes, 0)
            report["events"][1]["detail"]["route"]["model"] = "changed-returned-copy"
            self.assertEqual(inspect_history(ledger, "sample")["events"], self.expected_events)

    def test_exact_part_filter_keeps_empty_history_distinct_from_missing_part(self):
        with Ledger.open_readonly(self.database) as ledger:
            report = inspect_history(ledger, "sample", part_id="review")
            self.assertEqual(report["events"],
                             [row for row in self.expected_events if row["part_id"] == "review"])
            self.assertEqual(report["part_id"], "review")
            self.assertEqual(inspect_history(ledger, "sample", part_id="pending")["events"], [])
            with self.assertRaises(InspectionError) as caught:
                inspect_history(ledger, "sample", part_id="Review")
            self.assertEqual(caught.exception.code, "part_not_found")
            with self.assertRaises(InspectionError) as caught:
                inspect_history(ledger, "missing")
            self.assertEqual(caught.exception.code, "project_not_found")

    def test_real_cli_matches_api_and_preserves_existing_database(self):
        before = self.database.read_bytes()
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        with Ledger.open_readonly(self.database) as ledger:
            expected = (canonical_json(inspect_history(ledger, "sample")) + "\n").encode("utf-8")
        self.assertEqual(result.stdout, expected)
        self.assertEqual(self.database.read_bytes(), before)
        selected = self.cli("--part", "pending")
        self.assertEqual(selected.returncode, 0, selected.stderr)
        self.assertEqual(json.loads(selected.stdout)["events"], [])

    def test_missing_targets_and_unreadable_schema_emit_no_report(self):
        for arguments, code, diagnostic in [
            (("--project", "missing"), 3, b"project_not_found"),
            (("--part", "missing"), 3, b"part_not_found"),
        ]:
            with self.subTest(arguments=arguments):
                result = self.cli(*arguments)
                self.assertEqual(result.returncode, code)
                self.assertEqual(result.stdout, b"")
                self.assertIn(diagnostic, result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)
        absent = Path(self.temporary.name) / "absent.sqlite3"
        result = self.cli("--database", str(absent))
        self.assertEqual((result.returncode, result.stdout), (2, b""))
        self.assertFalse(absent.exists())
        empty = Path(self.temporary.name) / "empty.sqlite3"
        empty.touch()
        result = self.cli("--database", str(empty))
        self.assertEqual((result.returncode, result.stdout), (2, b""))
        self.assertEqual(empty.read_bytes(), b"")

    def test_invalid_late_events_refuse_even_when_part_filter_excludes_them(self):
        original = self.expected_events[-1]
        cases = [
            ("detail_json", "{"),
            ("detail_json", '{"finding":"first","finding":"second"}'),
            ("detail_json", '{"value":1e400}'),
            ("detail_json", sqlite3.Binary(b'{"value":"\xff"}')),
            ("event", ""),
            ("part_id", "outside-the-plan"),
            ("at", float("inf")),
            ("at", "invalid-time"),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                with closing(sqlite3.connect(self.database)) as db, db:
                    db.execute(f"UPDATE events SET {field}=? WHERE seq=?", (value, original["seq"]))
                before = self.database.read_bytes()
                result = self.cli("--part", "work")
                self.assertEqual((result.returncode, result.stdout), (2, b""), result.stderr)
                self.assertIn(b"invalid_record", result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)
                self.assertEqual(self.database.read_bytes(), before)
                with closing(sqlite3.connect(self.database)) as db, db:
                    db.execute(f"UPDATE events SET {field}=? WHERE seq=?",
                               (original[field], original["seq"]))

    def test_invalid_sequence_and_plan_identity_refuse_before_output(self):
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE events SET seq=-1 WHERE seq=11")
        result = self.cli()
        self.assertEqual((result.returncode, result.stdout), (2, b""))
        self.assertIn(b"invalid recording sequence", result.stderr)
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE events SET seq=11 WHERE seq=-1")
            db.execute("UPDATE projects SET plan_digest='wrong' WHERE project_id='sample'")
        result = self.cli()
        self.assertEqual((result.returncode, result.stdout), (2, b""))
        self.assertIn(b"recorded digest", result.stderr)

    def test_api_respects_callers_uncommitted_transaction_and_rollback(self):
        with Ledger(str(self.database)) as ledger:
            ledger._db.execute("BEGIN")
            ledger._db.execute("UPDATE events SET detail_json=? WHERE seq=11", ('{"pending":true}',))
            denied = {sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE, sqlite3.SQLITE_DELETE,
                      sqlite3.SQLITE_TRANSACTION}
            ledger._db.set_authorizer(
                lambda action, *_: sqlite3.SQLITE_DENY if action in denied else sqlite3.SQLITE_OK
            )
            try:
                report = inspect_history(ledger, "sample")
                self.assertEqual(report["events"][-1]["detail"], {"pending": True})
                self.assertTrue(ledger._db.in_transaction)
            finally:
                ledger._db.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
                ledger._db.rollback()
            self.assertEqual(inspect_history(ledger, "sample")["events"], self.expected_events)

    def test_cli_observes_committed_wal_events_without_recovery(self):
        with closing(sqlite3.connect(self.database, isolation_level=None)) as writer, writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
            writer.execute("BEGIN IMMEDIATE")
            writer.execute("UPDATE events SET detail_json=? WHERE seq=11", ('{"committed":true}',))
            before_commit = self.cli()
            self.assertEqual(before_commit.returncode, 0, before_commit.stderr)
            self.assertEqual(json.loads(before_commit.stdout)["events"], self.expected_events)
            writer.commit()
            after_commit = self.cli()
            self.assertEqual(after_commit.returncode, 0, after_commit.stderr)
            self.assertEqual(json.loads(after_commit.stdout)["events"][-1]["detail"], {"committed": True})
            self.assertEqual(writer.execute(
                "SELECT state FROM parts WHERE project_id='sample' AND part_id='interrupted'"
            ).fetchone()[0], "outcome_unknown")

    @unittest.skipUnless(os.path.exists("/dev/full"), "/dev/full is unavailable")
    def test_cli_reports_output_failure_cleanly(self):
        before = self.database.read_bytes()
        with open("/dev/full", "wb", buffering=0) as sink:
            result = self.cli(stdout=sink)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"cannot write report", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertEqual(self.database.read_bytes(), before)

    def test_new_output_matches_stdout_without_modifying_ledger(self):
        output = Path(self.temporary.name) / "history résumé.json"
        before = self.database.read_bytes()
        expected = self.cli("--part", "review")
        self.assertEqual(expected.returncode, 0, expected.stderr)
        result = self.cli("--part", "review", "--output", str(output))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        self.assertEqual(output.read_bytes(), expected.stdout)
        self.assertEqual(self.database.read_bytes(), before)
        self.assertEqual(list(Path(self.temporary.name).glob(".fanout-preview-*")), [])

    def test_output_destination_is_exclusive_and_errors_keep_existing_bytes(self):
        directory = Path(self.temporary.name)
        original = self.database.read_bytes()
        occupied = directory / "occupied.json"
        occupied.write_bytes(b"sentinel")
        symlink = directory / "linked.json"
        existing_dir = directory / "existing-dir"
        existing_dir.mkdir()
        destinations = [occupied, existing_dir, directory / "missing" / "new.json"]
        try:
            symlink.symlink_to(occupied)
        except (OSError, NotImplementedError):
            # Creating symlinks can require extra Windows permissions.
            pass
        else:
            destinations.append(symlink)
        for destination in destinations:
            with self.subTest(destination=destination):
                result = self.cli("--output", str(destination))
                self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
                self.assertIn(b"cannot write report", result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)
        self.assertEqual(occupied.read_bytes(), b"sentinel")
        if symlink.is_symlink():
            self.assertEqual(symlink.read_bytes(), b"sentinel")
        self.assertTrue(existing_dir.is_dir())
        self.assertFalse((directory / "missing").exists())
        self.assertEqual(self.database.read_bytes(), original)
        self.assertEqual(list(directory.glob(".fanout-preview-*")), [])

    def test_invalid_history_creates_no_output(self):
        output = Path(self.temporary.name) / "should-not-exist.json"
        before = self.database.read_bytes()
        result = self.cli("--part", "no-such-part", "--output", str(output))
        self.assertEqual((result.returncode, result.stdout), (3, b""), result.stderr)
        self.assertIn(b"part_not_found", result.stderr)
        self.assertFalse(output.exists())
        self.assertEqual(self.database.read_bytes(), before)

if __name__ == "__main__":
    unittest.main()
