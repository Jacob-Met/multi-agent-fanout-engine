"""Installed-style operator withdrawal without creating or repairing a ledger."""
from contextlib import closing, redirect_stderr
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fanout_engine import Ledger, Plan, inspect_project
from fanout_engine.plan import canonical_json
from fanout_engine import withdraw

ROOT = Path(__file__).resolve().parents[1]
PROJECT = "operator-fixture"
EVIDENCE = {"source": " caller decision ", "locator": "request:東京/2",
            "finding": "  The caller no longer requests this work.  "}


class WithdrawCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "work.sqlite3"
        self.seed(self.database)

    def seed(self, path):
        with Ledger(str(path)) as ledger:
            ledger.record_plan(Plan.from_dict({"project": PROJECT, "parts": [
                {"id": "build", "instruction": "Prepare local work."},
                {"id": "verify", "instruction": "Receive work.", "depends_on": ["build"]},
                {"id": "notes", "instruction": "Prepare separate notes."},
            ]}))

    def args(self, database=None, project=PROJECT, part="build", evidence=None):
        proof = EVIDENCE if evidence is None else evidence
        return ["--database", str(self.database if database is None else database),
                "--project", project, "--part", part,
                "--source", proof["source"], "--locator", proof["locator"],
                "--finding", proof["finding"]]

    def run_cli(self, args):
        bootstrap = ("import runpy,sys;sys.path.insert(0,sys.argv.pop(1));"
                     "runpy.run_module('fanout_engine.withdraw',run_name='__main__')")
        flags = ["-O"] if sys.flags.optimize else []
        return subprocess.run([sys.executable, "-I", "-B", *flags, "-c", bootstrap,
                               str(ROOT), *args], cwd=self.root,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    def refuse(self, args, database=None):
        path = self.database if database is None else database
        before = path.read_bytes() if path.is_file() else None
        result = self.run_cli(args)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertTrue(result.stderr)
        if before is not None:
            self.assertEqual(path.read_bytes(), before)
        else:
            self.assertFalse(path.is_file())
        return result

    def schema(self, database=None):
        with closing(sqlite3.connect(self.database if database is None else database)) as db:
            return db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name").fetchall()

    def test_literal_success_preserves_identity_schema_and_other_rows(self):
        schema = self.schema()
        with Ledger.open_readonly(self.database) as ledger:
            old_rows = {p: ledger.part(PROJECT, p) for p in ("build", "verify", "notes")}
        result = self.run_cli(self.args())
        expected = {"project_id": PROJECT, "part_id": "build", "state": "failed",
                    "event": "queued_withdrawn", "evidence": EVIDENCE}
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        self.assertEqual(result.stdout, (canonical_json(expected) + "\n").encode())
        self.assertEqual(self.schema(), schema)
        with Ledger.open_readonly(self.database) as ledger:
            current = ledger.part(PROJECT, "build")
            for key, value in old_rows["build"].items():
                if key not in {"state", "evidence", "evidence_json", "updated_at"}:
                    self.assertEqual(current[key], value, key)
            self.assertEqual(current["evidence"], EVIDENCE)
            for part in ("verify", "notes"):
                self.assertEqual(ledger.part(PROJECT, part), old_rows[part])
            events = ledger.events(PROJECT, "build")
            self.assertEqual([event["event"] for event in events], ["queued_withdrawn"])
            self.assertEqual(events[0]["detail"], EVIDENCE)
            report = inspect_project(ledger, PROJECT)
            self.assertEqual(report["blocked_queued_ids"], ["verify"])
            self.assertEqual(report["queued_ready_ids"], ["notes"])

    def test_blocked_queued_part_is_eligible(self):
        result = self.run_cli(self.args(part="verify"))
        self.assertEqual(result.returncode, 0, result.stderr)
        with Ledger.open_readonly(self.database) as ledger:
            self.assertEqual(ledger.part_state(PROJECT, "verify"), "failed")
            self.assertEqual(ledger.part_state(PROJECT, "build"), "queued")

    def test_repeat_and_unknown_project_or_part_refuse(self):
        self.assertEqual(self.run_cli(self.args()).returncode, 0)
        for args in (self.args(), self.args(project="missing"), self.args(part="missing")):
            with self.subTest(args=args):
                self.refuse(args)

    def test_other_native_states_refuse(self):
        for state in ("dispatching", "running", "outcome_unknown", "completed", "failed"):
            path = self.root / (state + ".sqlite3")
            self.seed(path)
            with Ledger.open_existing(path) as ledger:
                ledger.mark_dispatching(PROJECT, "build", "worker", {"model": "local", "effort": "low"})
                if state != "dispatching":
                    ledger.mark_running(PROJECT, "build", "task")
                if state == "outcome_unknown":
                    ledger.mark_outcome_unknown(PROJECT, "build", EVIDENCE)
                elif state == "completed":
                    ledger.mark_completed(PROJECT, "build", "fixture:artifact", EVIDENCE)
                elif state == "failed":
                    ledger.mark_failed(PROJECT, "build", EVIDENCE)
            with self.subTest(state=state):
                self.refuse(self.args(database=path), path)

    def test_queued_submission_and_artifact_references_refuse(self):
        for column in ("worker_id", "task_id", "route_json", "artifact_ref"):
            path = self.root / (column + ".sqlite3")
            self.seed(path)
            with closing(sqlite3.connect(path)) as db:
                db.execute(f"UPDATE parts SET {column}=? WHERE part_id='build'",
                           ('{"model":"retained"}' if column == "route_json" else "",))
                db.commit()
            with self.subTest(column=column):
                self.refuse(self.args(database=path), path)

    def test_blank_evidence_and_usage_refuse(self):
        for name in EVIDENCE:
            with self.subTest(name=name):
                self.refuse(self.args(evidence={**EVIDENCE, name: " \t"}))
        self.refuse(self.args()[:-2])
        args = self.args()
        args[0] = "--dat"
        self.refuse(args)

    def test_missing_empty_foreign_non_sqlite_and_directory_do_not_initialize(self):
        paths = [self.root / "missing", self.root / "empty",
                 self.root / "foreign", self.root / "text", self.root / "directory"]
        paths[1].write_bytes(b"")
        with closing(sqlite3.connect(paths[2])) as db:
            db.execute("CREATE TABLE unrelated(value TEXT)")
            db.commit()
        paths[3].write_bytes(b"not a SQLite database\n")
        paths[4].mkdir()
        for path in paths:
            with self.subTest(path=path.name):
                self.refuse(self.args(database=path), path)
        self.assertEqual(list(paths[4].iterdir()), [])

    def test_native_identity_or_missing_schema_refuses_unchanged(self):
        updates = [
            ("payload", "UPDATE parts SET payload_json='{}' WHERE part_id='build'"),
            ("key", "UPDATE parts SET idempotency_key='wrong' WHERE part_id='build'"),
            ("plan", "UPDATE projects SET plan_digest='wrong'"),
            ("events", "DROP TABLE events"),
        ]
        for name, sql in updates:
            path = self.root / (name + ".sqlite3")
            self.seed(path)
            with closing(sqlite3.connect(path)) as db:
                db.execute(sql)
                db.commit()
            with self.subTest(name=name):
                self.refuse(self.args(database=path), path)

    def test_literal_path_and_missing_index_are_supported_without_schema_repair(self):
        path = self.root / "ledger # % 雪.sqlite3"
        self.seed(path)
        with closing(sqlite3.connect(path)) as db:
            db.execute("DROP INDEX events_project_id")
            db.commit()
        schema = self.schema(path)
        result = self.run_cli(self.args(database=path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.schema(path), schema)

    def test_unencodable_confirmation_refuses_before_database_open(self):
        before = self.database.read_bytes()
        stderr = io.StringIO()
        with patch.object(Ledger, "open_existing") as opener, redirect_stderr(stderr):
            code = withdraw.main(self.args(evidence={**EVIDENCE, "finding": "\ud800"}))
        self.assertEqual(code, 2)
        opener.assert_not_called()
        self.assertTrue(stderr.getvalue())
        self.assertEqual(self.database.read_bytes(), before)

    def test_output_failure_reports_committed_and_repeat_does_not_add_event(self):
        stderr = io.StringIO()
        with patch.object(withdraw, "_write_stdout", side_effect=OSError("fixture output failure")), redirect_stderr(stderr):
            code = withdraw.main(self.args())
        self.assertEqual(code, 1)
        self.assertIn("withdrawal committed", stderr.getvalue())
        self.assertIn("history before retrying", stderr.getvalue())
        with Ledger.open_readonly(self.database) as ledger:
            self.assertEqual(ledger.part_state(PROJECT, "build"), "failed")
            self.assertEqual(len(ledger.events(PROJECT, "build")), 1)
        self.refuse(self.args())

    @unittest.skipUnless(os.name == "posix", "requires POSIX child descriptor control")
    def test_closed_stdout_reports_committed_without_traceback(self):
        bootstrap = ("import runpy,sys;sys.path.insert(0,sys.argv.pop(1));"
                     "runpy.run_module('fanout_engine.withdraw',run_name='__main__')")
        flags = ["-O"] if sys.flags.optimize else []
        result = subprocess.run(
            [sys.executable, "-I", "-B", *flags, "-c", bootstrap, str(ROOT), *self.args()],
            cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            preexec_fn=lambda: os.close(1), check=False,
        )
        self.assertEqual((result.returncode, result.stdout), (1, b""))
        self.assertIn(b"withdrawal committed", result.stderr)
        self.assertIn(b"standard output is unavailable", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        with Ledger.open_readonly(self.database) as ledger:
            self.assertEqual(ledger.part_state(PROJECT, "build"), "failed")
            self.assertEqual(len(ledger.events(PROJECT, "build")), 1)

    def test_existing_file_open_never_initializes_an_empty_database(self):
        path = self.root / "empty-open.sqlite3"
        path.write_bytes(b"")
        with Ledger.open_existing(path) as ledger:
            self.assertEqual(ledger._db.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(ledger._db.execute("SELECT * FROM sqlite_master").fetchall(), [])
        self.assertEqual(path.read_bytes(), b"")

    def test_sqlite_rw_mode_refuses_missing_file_even_after_positive_precheck(self):
        path = self.root / "vanished.sqlite3"
        with patch.object(Path, "is_file", return_value=True):
            with self.assertRaises(sqlite3.OperationalError):
                Ledger.open_existing(path)
        self.assertFalse(path.exists())

    def test_failed_existing_file_setup_closes_real_connection(self):
        class SetupFailure(BaseException):
            pass

        class Connection(sqlite3.Connection):
            def execute(self, sql, *args, **kwargs):
                if sql == "PRAGMA foreign_keys=ON":
                    raise SetupFailure("fixture setup interruption")
                return super().execute(sql, *args, **kwargs)

        connection = sqlite3.connect(":memory:", factory=Connection)
        with patch("fanout_engine.ledger.sqlite3.connect", return_value=connection):
            with self.assertRaises(SetupFailure):
                Ledger.open_existing(self.database)
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")


if __name__ == "__main__":
    unittest.main()
