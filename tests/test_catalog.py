"""Discover stored plan IDs before selecting a project for inspection."""
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

from fanout_engine import InspectionError, Ledger, Part, Plan, canonical_json, inspect_project
from fanout_engine.catalog import catalog_projects


ROOT = Path(__file__).resolve().parents[1]


class CatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="fanout-catalog-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        punctuation = "#&=%" if os.name == "nt" else "#?&=%"
        self.database = self.directory / f"retained {punctuation} café.sqlite3"
        self.plans = [
            Plan("zeta", (Part("notes", "An independent authored project."),)),
            Plan("alpha", (Part("one", "A case-distinct project."),)),
            Plan("Alpha", (
                Part("review", "Review 日本語 sources.", ("second", "first"), ("z", "a", "z")),
                Part("first", "First independent source."),
                Part("second", "Second independent source."),
            )),
        ]
        with Ledger(str(self.database)) as ledger:
            for plan in self.plans:
                ledger.record_plan(plan)
        self.expected = {
            "schema_version": 1,
            "projects": [{"project_id": plan.project_id, "plan_digest": plan.digest,
                          "declared_part_count": len(plan.parts)}
                         for plan in sorted(self.plans, key=lambda item: item.project_id)],
        }

    def run_cli(self, database: Path | None = None, *extra: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.catalog",
             "--database", str(database or self.database), *extra],
            cwd=ROOT, capture_output=True, timeout=10,
        )

    def test_catalog_uses_exact_native_ids_digests_and_declared_counts(self) -> None:
        before = self.database.read_bytes()
        with Ledger.open_readonly(self.database) as ledger:
            statements = []
            ledger._db.set_trace_callback(statements.append)
            report = catalog_projects(ledger)
            self.assertEqual(len(statements), 1, statements)
            self.assertTrue(statements[0].lstrip().upper().startswith("SELECT "))
            ledger._db.set_trace_callback(None)
            self.assertEqual(report, self.expected)
            for row in report["projects"]:
                detailed = inspect_project(ledger, row["project_id"])
                self.assertEqual(detailed["plan_digest"], row["plan_digest"])
                self.assertEqual(len(detailed["parts"]), row["declared_part_count"])
            report["projects"][0]["project_id"] = "caller-edit"
            self.assertEqual(catalog_projects(ledger), self.expected)
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.stdout, (canonical_json(self.expected) + "\n").encode("utf-8"))
        self.assertEqual(self.database.read_bytes(), before)

    def test_empty_headers_are_valid_and_do_not_certify_other_tables(self) -> None:
        empty = self.directory / "empty-ledger.sqlite3"
        with Ledger(str(empty)):
            pass
        for database in (empty, self.directory / "headers-only.sqlite3"):
            if database != empty:
                with closing(sqlite3.connect(database)) as connection, connection:
                    connection.execute("CREATE TABLE projects(project_id TEXT, plan_digest TEXT, plan_json TEXT)")
            before = database.read_bytes()
            result = self.run_cli(database)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"schema_version": 1, "projects": []})
            self.assertEqual(database.read_bytes(), before)

    def test_bad_header_refuses_whole_catalog_before_output(self) -> None:
        for column, value in (("plan_json", "invalid JSON"), ("plan_digest", "0" * 64)):
            with self.subTest(column=column):
                with closing(sqlite3.connect(self.database)) as connection, connection:
                    original = connection.execute(f"SELECT {column} FROM projects WHERE project_id='zeta'").fetchone()[0]
                    connection.execute(f"UPDATE projects SET {column}=? WHERE project_id='zeta'", (value,))
                before = self.database.read_bytes()
                destination = self.directory / "not-published.json"
                result = self.run_cli(None, "--output", str(destination))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"invalid_record", result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)
                self.assertFalse(destination.exists())
                self.assertEqual(self.database.read_bytes(), before)
                self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])
                with closing(sqlite3.connect(self.database)) as connection, connection:
                    connection.execute(f"UPDATE projects SET {column}=? WHERE project_id='zeta'", (original,))

    def test_duplicate_stored_headers_are_not_a_valid_catalog(self) -> None:
        duplicate = self.directory / "duplicate.sqlite3"
        plan = self.plans[0]
        with closing(sqlite3.connect(duplicate)) as connection, connection:
            connection.execute("CREATE TABLE projects(project_id TEXT, plan_digest TEXT, plan_json TEXT)")
            connection.executemany("INSERT INTO projects VALUES (?,?,?)", [
                (plan.project_id, plan.digest, canonical_json(plan.to_dict())),
                (plan.project_id, plan.digest, canonical_json(plan.to_dict())),
            ])
        with Ledger.open_readonly(duplicate) as ledger:
            with self.assertRaises(InspectionError) as refused:
                catalog_projects(ledger)
            self.assertEqual(refused.exception.code, "invalid_record")
        result = self.run_cli(duplicate)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"repeated identifier", result.stderr)

    def test_declared_count_does_not_inspect_or_repair_retained_part_rows(self) -> None:
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("DELETE FROM parts WHERE project_id='Alpha' AND part_id='first'")
        before = self.database.read_bytes()
        with Ledger.open_readonly(self.database) as ledger:
            self.assertEqual(catalog_projects(ledger), self.expected)
            with self.assertRaises(InspectionError) as refused:
                inspect_project(ledger, "Alpha")
            self.assertEqual(refused.exception.code, "missing_parts")
        self.assertEqual(self.database.read_bytes(), before)

    def test_header_read_does_not_commit_a_callers_open_transaction(self) -> None:
        with Ledger(str(self.database)) as ledger:
            ledger._db.execute("BEGIN IMMEDIATE")
            ledger._db.execute("DELETE FROM parts WHERE project_id='alpha'")
            ledger._db.execute("DELETE FROM projects WHERE project_id='alpha'")
            changes = ledger._db.total_changes
            observed = catalog_projects(ledger)
            self.assertEqual([row["project_id"] for row in observed["projects"]], ["Alpha", "zeta"])
            self.assertTrue(ledger._db.in_transaction)
            self.assertEqual(ledger._db.total_changes, changes)
            ledger._db.rollback()
            self.assertEqual(catalog_projects(ledger), self.expected)

    def test_missing_and_incompatible_databases_are_not_initialized(self) -> None:
        missing = self.directory / "missing.sqlite3"
        foreign = self.directory / "foreign.sqlite3"
        foreign.touch()
        for database in (missing, foreign):
            result = self.run_cli(database)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"cannot read ledger", result.stderr)
        self.assertFalse(missing.exists())
        self.assertEqual(foreign.read_bytes(), b"")

    def test_fresh_export_uses_existing_protected_file_delivery(self) -> None:
        destination = self.directory / "catalog.json"
        result = self.run_cli(None, "--output", str(destination))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")
        expected = (canonical_json(self.expected) + "\n").encode("utf-8")
        self.assertEqual(destination.read_bytes(), expected)
        occupied = self.run_cli(None, "--output", str(destination))
        self.assertEqual(occupied.returncode, 1)
        self.assertEqual(destination.read_bytes(), expected)
        sidecar = Path(str(self.database) + "-wal")
        protected = self.run_cli(None, "--output", str(sidecar))
        self.assertEqual(protected.returncode, 1)
        self.assertIn(b"SQLite sidecar", protected.stderr)
        self.assertFalse(sidecar.exists())
        self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])


if __name__ == "__main__":
    unittest.main()
