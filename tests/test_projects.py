"""Project discovery through native SQLite and the actual module CLI."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from fanout_engine import Ledger, Part, Plan, canonical_json, inspect_project
from fanout_engine.inspection import InspectionError
from fanout_engine.projects import list_projects

ROOT = Path(__file__).resolve().parents[1]


def make_plan(project, count=1):
    return Plan(project, tuple(
        Part("part-" + str(index), "Read authored input " + str(index),
             tags=("saved", "saved"))
        for index in range(count)
    ))


class ProjectCatalogTests(unittest.TestCase):
    def test_empty_and_sorted_catalog_matches_native_plan_identities(self):
        with Ledger() as ledger:
            self.assertEqual(list_projects(ledger), {
                "schema_version": 1, "project_count": 0, "projects": [],
            })
            plans = [make_plan("zulu", 3), make_plan("alpha", 2), make_plan("Bravo")]
            for plan in plans:
                ledger.record_plan(plan)
            changes = ledger._db.total_changes
            expected = {
                "schema_version": 1, "project_count": 3,
                "projects": [
                    {"project_id": plan.project_id, "plan_digest": plan.digest,
                     "part_count": len(plan.parts)}
                    for plan in (plans[2], plans[1], plans[0])
                ],
            }
            self.assertEqual(list_projects(ledger), expected)
            self.assertEqual(ledger._db.total_changes, changes)
            for entry in expected["projects"]:
                report = inspect_project(ledger, entry["project_id"])
                self.assertEqual(report["plan_digest"], entry["plan_digest"])
                self.assertEqual(len(report["parts"]), entry["part_count"])

    def test_one_snapshot_and_detached_results(self):
        with Ledger() as ledger:
            ledger.record_plan(make_plan("saved"))
            statements = []
            ledger._db.set_trace_callback(statements.append)
            report = list_projects(ledger)
            ledger._db.set_trace_callback(None)
            self.assertEqual(len(statements), 1)
            self.assertTrue(statements[0].lstrip().upper().startswith("SELECT"))
            expected = json.loads(canonical_json(report))
            report["projects"][0]["project_id"] = "changed"
            report["projects"].append({"project_id": "invented"})
            self.assertEqual(list_projects(ledger), expected)
            snapshot = ledger.project_catalog_snapshot()
            snapshot[0]["plan_json"] = "{}"
            self.assertEqual(list_projects(ledger), expected)

    def test_catalog_does_not_complete_a_callers_transaction(self):
        plan = make_plan("pending")
        with Ledger() as ledger:
            ledger._db.execute("BEGIN")
            ledger._db.execute(
                "INSERT INTO projects(project_id,plan_digest,plan_json) VALUES(?,?,?)",
                (plan.project_id, plan.digest, canonical_json(plan.to_dict())),
            )
            self.assertEqual(list_projects(ledger)["projects"][0]["project_id"], "pending")
            self.assertTrue(ledger._db.in_transaction)
            ledger._db.rollback()
            self.assertEqual(list_projects(ledger)["projects"], [])

    def test_invalid_later_plan_refuses_complete_catalog(self):
        invalid_values = [
            ("plan_json", "{}"),
            ("plan_json", '{"project":"zulu","project":"zulu","parts":[]}'),
            ("plan_json", '{"project":"zulu","parts":[{"id":"p","instruction":NaN}]}'),
            ("plan_digest", "0" * 64),
            ("plan_json", canonical_json(make_plan("other").to_dict())),
        ]
        for column, value in invalid_values:
            with self.subTest(column=column, value=value), Ledger() as ledger:
                ledger.record_plan(make_plan("Alpha"))
                ledger.record_plan(make_plan("zulu"))
                ledger._db.execute(
                    "UPDATE projects SET " + column + "=? WHERE project_id='zulu'",
                    (value,),
                )
                with self.assertRaises(InspectionError) as caught:
                    list_projects(ledger)
                self.assertEqual(caught.exception.code, "invalid_record")

    def test_catalog_projects_plans_without_reading_runtime_rows(self):
        with Ledger() as ledger:
            plan = make_plan("saved", 2)
            ledger.record_plan(plan)
            ledger._db.execute("UPDATE parts SET payload_json='not JSON'")
            reads = []
            def authorizer(action, table, column, database, trigger):
                if action == sqlite3.SQLITE_READ:
                    reads.append((table, column))
                    if table != "projects":
                        return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            ledger._db.set_authorizer(authorizer)
            report = list_projects(ledger)
            ledger._db.set_authorizer(None)
            self.assertEqual(report["projects"], [{
                "project_id": "saved", "plan_digest": plan.digest, "part_count": 2,
            }])
            self.assertTrue(reads)
            self.assertEqual({table for table, column in reads}, {"projects"})
            with self.assertRaises(InspectionError):
                inspect_project(ledger, "saved")

    def test_database_errors_propagate_from_native_api(self):
        ledger = Ledger()
        ledger.close()
        with self.assertRaises(sqlite3.ProgrammingError):
            list_projects(ledger)


class ProjectCatalogCliTests(unittest.TestCase):
    def command(self, module, *args):
        options = ["-O"] if sys.flags.optimize else []
        return subprocess.run(
            [sys.executable, "-B", *options, "-m", module, *map(str, args)],
            cwd=ROOT, capture_output=True, timeout=20,
        )

    def seed(self, path):
        with Ledger(str(path)) as ledger:
            ledger.record_plan(make_plan("zulu", 2))
            ledger.record_plan(make_plan("Alpha"))
            return list_projects(ledger)

    def test_real_cli_catalog_then_known_project_inspection(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "saved Ω # & %.sqlite3"
            expected = self.seed(database)
            before = database.read_bytes()
            result = self.command("fanout_engine.projects", "--database", database)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, b"")
            self.assertEqual(result.stdout, (canonical_json(expected) + "\n").encode("utf-8"))
            for entry in json.loads(result.stdout)["projects"]:
                inspected = self.command(
                    "fanout_engine.inspect", "--database", database,
                    "--project", entry["project_id"],
                )
                self.assertEqual(inspected.returncode, 0, inspected.stderr)
                report = json.loads(inspected.stdout)
                self.assertEqual(report["plan_digest"], entry["plan_digest"])
                self.assertEqual(len(report["parts"]), entry["part_count"])
            self.assertEqual(database.read_bytes(), before)

    def test_new_file_export_and_occupied_destinations(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "saved.sqlite3"
            expected = self.seed(database)
            before = database.read_bytes()
            output = Path(directory) / "catalog 東京.json"
            result = self.command(
                "fanout_engine.projects", "--database", database, "--output", output,
            )
            content = (canonical_json(expected) + "\n").encode("utf-8")
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
            self.assertEqual(output.read_bytes(), content)
            for occupied in (output, database, Path(directory)):
                refusal = self.command(
                    "fanout_engine.projects", "--database", database, "--output", occupied,
                )
                self.assertEqual(refusal.returncode, 1, refusal.stderr)
                self.assertEqual(refusal.stdout, b"")
            self.assertEqual(output.read_bytes(), content)
            self.assertEqual(database.read_bytes(), before)
            absent_parent = Path(directory) / "absent" / "catalog.json"
            refusal = self.command(
                "fanout_engine.projects", "--database", database, "--output", absent_parent,
            )
            self.assertEqual(refusal.returncode, 1, refusal.stderr)
            self.assertFalse(absent_parent.parent.exists())

    def test_bad_inputs_never_publish_a_partial_catalog(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            good = root / "saved.sqlite3"
            self.seed(good)
            with closing(sqlite3.connect(good)) as connection, connection:
                connection.execute("UPDATE projects SET plan_json='{}' WHERE project_id='zulu'")
            empty = root / "empty.sqlite3"
            empty.write_bytes(b"")
            foreign = root / "foreign.sqlite3"
            foreign.write_bytes(b"not a SQLite database")
            missing = root / "missing.sqlite3"
            for source in (good, empty, foreign, missing, root):
                with self.subTest(source=source):
                    output = root / "unpublished.json"
                    result = self.command(
                        "fanout_engine.projects", "--database", source, "--output", output,
                    )
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, b"")
                    self.assertFalse(output.exists())
            self.assertFalse(missing.exists())
            result = self.command("fanout_engine.projects", "--database", good)
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"invalid_record", result.stderr)
            self.assertEqual(result.stdout, b"")

    def test_empty_ledger_and_strict_cli_options(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "empty-ledger.sqlite3"
            with Ledger(str(database)):
                pass
            result = self.command("fanout_engine.projects", "--database", database)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {
                "schema_version": 1, "project_count": 0, "projects": [],
            })
            for args in ((), ("--data", database), ("--database", database, "--unknown")):
                with self.subTest(args=args):
                    result = self.command("fanout_engine.projects", *args)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, b"")

    def test_readonly_catalog_sees_only_committed_wal_changes(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "active.sqlite3"
            with Ledger(str(database)) as writer:
                self.assertEqual(writer._db.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
                writer.record_plan(make_plan("Alpha"))
                with Ledger.open_readonly(database) as reader:
                    self.assertEqual(list_projects(reader)["project_count"], 1)
                    plan = make_plan("Bravo", 2)
                    writer._db.execute("BEGIN IMMEDIATE")
                    writer._db.execute(
                        "INSERT INTO projects(project_id,plan_digest,plan_json) VALUES(?,?,?)",
                        (plan.project_id, plan.digest, canonical_json(plan.to_dict())),
                    )
                    self.assertEqual(list_projects(reader)["project_count"], 1)
                    writer._db.commit()
                    self.assertEqual(
                        [entry["project_id"] for entry in list_projects(reader)["projects"]],
                        ["Alpha", "Bravo"],
                    )
                    self.assertEqual(reader._db.total_changes, 0)


if __name__ == "__main__":
    unittest.main()
