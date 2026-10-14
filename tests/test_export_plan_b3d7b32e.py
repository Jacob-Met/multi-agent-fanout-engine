"""Real-file and CLI receiving for read-only native plan export."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from fanout_engine.export_plan import export_plan
from fanout_engine.inspection import InspectionError
from fanout_engine.ledger import Ledger
from fanout_engine.plan import Part, Plan


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


class ExportPlanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fanout-export-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = Path(__file__).resolve().parents[1]
        self.plan = Plan("export-example", (
            Part("joined", " Read the retained plan — Ω\nThen review. ",
                 ("second", "first"), ("zeta", "alpha", "zeta")),
            Part("first", "First input"),
            Part("second", "Second input"),
        ))
        self.document = {
            "project": "export-example",
            "parts": [
                {"id": "joined", "instruction": " Read the retained plan — Ω\nThen review. ",
                 "depends_on": ["second", "first"], "tags": ["zeta", "alpha", "zeta"]},
                {"id": "first", "instruction": "First input", "depends_on": [], "tags": []},
                {"id": "second", "instruction": "Second input", "depends_on": [], "tags": []},
            ],
        }
        self.database = self.seed("retained.sqlite3")

    def seed(self, name, plan=None):
        path = self.root / name
        with Ledger(path) as ledger:
            ledger.record_plan(self.plan if plan is None else plan)
        return path

    def command(self, database=None, project="export-example", output=None, **kwargs):
        args = ["fanout_engine.export_plan", "--database",
                str(self.database if database is None else database),
                "--project", project]
        if output is not None:
            args += ["--output", str(output)]
        return self.module(args, **kwargs)

    def module(self, args, **kwargs):
        flags = ["-O"] if sys.flags.optimize else []
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.source)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run([sys.executable, *flags, "-B", "-m", *args],
                              cwd=self.root, env=env, capture_output=True, **kwargs)

    def rewrite(self, sql, values=(), database=None):
        with sqlite3.connect(self.database if database is None else database) as db:
            db.execute(sql, values)

    def test_native_constructor_order_repeats_and_detachment(self):
        before = self.database.read_bytes()
        with Ledger.open_readonly(self.database) as ledger:
            result = export_plan(ledger, "export-example")
            self.assertEqual(result, self.document)
            self.assertEqual(hashlib.sha256(encoded(result)[:-1]).hexdigest(), self.plan.digest)
            result["parts"][0]["tags"].append("different")
            result["parts"].reverse()
            self.assertEqual(export_plan(ledger, "export-example"), self.document)
        self.assertEqual(self.database.read_bytes(), before)

    def test_read_preserves_callers_uncommitted_transaction(self):
        with Ledger(self.database) as ledger:
            ledger._db.execute("BEGIN IMMEDIATE")
            ledger._db.execute("UPDATE parts SET evidence_json='uncommitted'")
            self.assertEqual(export_plan(ledger, "export-example"), self.document)
            self.assertTrue(ledger._db.in_transaction)
            ledger._db.rollback()
            self.assertTrue(all(r[0] is None for r in ledger._db.execute(
                "SELECT evidence_json FROM parts")))

    def test_missing_project_has_existing_native_error_code(self):
        before = self.database.read_bytes()
        with Ledger.open_readonly(self.database) as ledger:
            with self.assertRaises(InspectionError) as caught:
                export_plan(ledger, "unknown")
        self.assertEqual(caught.exception.code, "project_not_found")
        self.assertEqual(self.database.read_bytes(), before)

    def test_malformed_headers_are_refused_without_normalizing_them(self):
        mutations = [
            ("UPDATE projects SET plan_digest=?", ("wrong",)),
            ("UPDATE projects SET plan_json=?", ('{"project":"export-example","parts":[]}',)),
            ("UPDATE projects SET plan_json=?", ('{"project":"export-example","project":"export-example","parts":[]}',)),
            ("UPDATE projects SET plan_json=?", ("not JSON",)),
            ("UPDATE projects SET project_id=?", ("other-identity",)),
        ]
        for index, (sql, values) in enumerate(mutations):
            with self.subTest(index=index):
                path = self.seed("invalid-%d.sqlite3" % index)
                self.rewrite(sql, values, path)
                before = path.read_bytes()
                with Ledger.open_readonly(path) as ledger:
                    with self.assertRaises(InspectionError) as caught:
                        export_plan(ledger, "other-identity" if index == 4 else "export-example")
                self.assertEqual(caught.exception.code, "invalid_record")
                self.assertEqual(path.read_bytes(), before)

    def test_runtime_state_and_evidence_are_not_plan_admission(self):
        self.rewrite("UPDATE parts SET state='failed',evidence_json='not JSON'")
        self.rewrite("DELETE FROM parts WHERE part_id='second'")
        self.rewrite("UPDATE events SET detail_json='not JSON'")
        before = self.database.read_bytes()
        with Ledger.open_readonly(self.database) as ledger:
            self.assertEqual(export_plan(ledger, "export-example"), self.document)
        self.assertEqual(self.database.read_bytes(), before)

    def test_other_project_header_is_not_read_or_exported(self):
        with Ledger(self.database) as ledger:
            ledger.record_plan(Plan("other", (Part("only", "Other project"),)))
        self.rewrite("UPDATE projects SET plan_digest='broken' WHERE project_id='other'")
        before = self.database.read_bytes()
        result = self.command()
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, encoded(self.document), b""))
        self.assertEqual(self.database.read_bytes(), before)

    def test_stdout_and_literal_uri_looking_filename(self):
        path = self.seed("file:literal?mode=memory#Ω.sqlite3")
        before = path.read_bytes()
        result = self.command(path)
        self.assertEqual((result.returncode, result.stdout, result.stderr),
                         (0, encoded(self.document), b""))
        self.assertEqual(path.read_bytes(), before)

    def test_new_file_and_existing_compare_consumer(self):
        ordinary = copy.deepcopy(self.document)
        ordinary["parts"][0]["tags"] = ["alpha", "zeta"]
        path = self.seed("ordinary.sqlite3", Plan.from_dict(ordinary))
        original = path.read_bytes()
        output = self.root / "recorded-plan.json"
        result = self.command(path, output=output)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        self.assertEqual(output.read_bytes(), encoded(ordinary))
        after = copy.deepcopy(ordinary)
        after["parts"][0]["instruction"] += " An authored revision."
        revised = self.root / "revised-plan.json"
        revised.write_bytes(encoded(after))
        comparison = self.module(["fanout_engine.compare", "--before", str(output),
                                  "--after", str(revised)])
        self.assertEqual((comparison.returncode, comparison.stderr), (0, b""))
        report = json.loads(comparison.stdout)
        self.assertEqual(report["before"]["plan"], ordinary)
        self.assertEqual(report["after"]["plan"], after)
        self.assertNotEqual(report["before"]["plan_digest"], report["after"]["plan_digest"])
        self.assertEqual(output.read_bytes(), encoded(ordinary))
        self.assertEqual(path.read_bytes(), original)

    def test_occupied_output_and_database_alias_are_preserved(self):
        occupied = self.root / "occupied.json"
        occupied.write_bytes(b"Existing reader-owned bytes.\n")
        for output in (occupied, self.database):
            with self.subTest(output=output.name):
                previous = output.read_bytes()
                database = self.database.read_bytes()
                result = self.command(output=output)
                self.assertEqual((result.returncode, result.stdout), (1, b""))
                self.assertIn(b"cannot write plan", result.stderr)
                self.assertEqual(output.read_bytes(), previous)
                self.assertEqual(self.database.read_bytes(), database)

    def test_reserved_sqlite_sidecar_names_are_not_published(self):
        before = self.database.read_bytes()
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                output = Path(str(self.database) + suffix)
                self.assertFalse(os.path.lexists(output))
                result = self.command(output=output)
                self.assertEqual((result.returncode, result.stdout), (1, b""))
                self.assertIn(b"SQLite sidecar", result.stderr)
                self.assertFalse(os.path.lexists(output))
                self.assertEqual(self.database.read_bytes(), before)

    def test_missing_database_and_parent_are_never_created(self):
        for path in (self.root / "missing.sqlite3",
                     self.root / "absent-parent" / "missing.sqlite3"):
            with self.subTest(path=path):
                result = self.command(path)
                self.assertEqual((result.returncode, result.stdout), (2, b""))
                self.assertFalse(path.exists())
                self.assertFalse((self.root / "absent-parent").exists())

    def test_empty_foreign_and_non_sqlite_files_are_preserved(self):
        empty = self.root / "empty.sqlite3"; empty.write_bytes(b"")
        text = self.root / "ordinary.txt"; text.write_bytes(b"not a database")
        foreign = self.root / "foreign.sqlite3"
        with sqlite3.connect(foreign) as db:
            db.execute("CREATE TABLE unrelated(value TEXT)")
        for path in (empty, text, foreign):
            with self.subTest(path=path.name):
                previous = path.read_bytes()
                result = self.command(path)
                self.assertEqual((result.returncode, result.stdout), (2, b""))
                self.assertEqual(path.read_bytes(), previous)

    def test_bad_header_and_unknown_project_create_no_output(self):
        self.rewrite("UPDATE projects SET plan_digest='wrong'")
        before = self.database.read_bytes()
        for project in ("export-example", "missing"):
            with self.subTest(project=project):
                output = self.root / (project + ".json")
                result = self.command(project=project, output=output)
                self.assertEqual((result.returncode, result.stdout), (2, b""))
                self.assertFalse(output.exists())
                self.assertEqual(self.database.read_bytes(), before)

    def test_missing_output_parent_is_not_created(self):
        output = self.root / "absent-output" / "plan.json"
        before = self.database.read_bytes()
        result = self.command(output=output)
        self.assertEqual((result.returncode, result.stdout), (1, b""))
        self.assertFalse(output.parent.exists())
        self.assertEqual(self.database.read_bytes(), before)

    @unittest.skipUnless(os.name == "posix", "real closed stdout requires POSIX")
    def test_real_closed_stdout_refuses_cleanly(self):
        before = self.database.read_bytes()
        result = self.command(preexec_fn=lambda: os.close(1))
        self.assertEqual((result.returncode, result.stdout), (1, b""))
        self.assertIn(b"cannot write plan", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertEqual(self.database.read_bytes(), before)

    @unittest.skipUnless(Path("/dev/full").exists(), "full output device unavailable")
    def test_real_full_stdout_preserves_database(self):
        before = self.database.read_bytes()
        flags = ["-O"] if sys.flags.optimize else []
        env = os.environ.copy();env["PYTHONPATH"] = str(self.source)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        with open("/dev/full", "wb") as stream:
            result = subprocess.run([sys.executable, *flags, "-B", "-m",
                "fanout_engine.export_plan", "--database", str(self.database),
                "--project", "export-example"], cwd=self.root, env=env,
                stdout=stream, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"cannot write plan", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertEqual(self.database.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
