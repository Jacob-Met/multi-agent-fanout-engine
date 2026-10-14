import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import InspectionError, Ledger, Part, Plan
from fanout_engine.blockers import inspect_blockers


REPO = Path(__file__).resolve().parents[1]


def plan_for(*entries, project="authored-project"):
    return Plan(project, tuple(
        Part(name, "Perform authored " + name + ".", tuple(dependencies))
        for name, dependencies in entries
    ))


def set_state(ledger, plan, part_id, state):
    if state == "queued":
        return
    ledger.mark_dispatching(plan.project_id, part_id, "worker-" + part_id,
                            {"model": "local-reference", "effort": "low"})
    if state == "dispatching":
        return
    ledger.mark_running(plan.project_id, part_id, "task-" + part_id)
    evidence = {"source": "authored fixture", "locator": "fixture:" + part_id,
                "finding": "explicit " + state + " control"}
    if state == "completed":
        ledger.mark_completed(plan.project_id, part_id, "fixture:artifact-" + part_id)
    elif state == "failed":
        ledger.mark_failed(plan.project_id, part_id, evidence)
    elif state == "outcome_unknown":
        ledger.mark_outcome_unknown(plan.project_id, part_id, evidence)


class BlockerTests(unittest.TestCase):
    def test_all_ready_work_has_no_blocking_frontier(self):
        plan = plan_for(("z", ()), ("a", ()))
        with Ledger() as ledger:
            ledger.record_plan(plan)
            report = inspect_blockers(ledger, plan.project_id)
        self.assertEqual(report, {
            "schema_version": 1, "project_id": plan.project_id, "plan_digest": plan.digest,
            "queued_ready_ids": ["z", "a"], "blocked_queued": [], "frontier": [],
        })

    def test_queued_chain_reaches_ready_work_in_reverse_declaration_order(self):
        plan = plan_for(("leaf", ("middle",)), ("middle", ("root",)), ("root", ()))
        with Ledger() as ledger:
            ledger.record_plan(plan)
            report = inspect_blockers(ledger, plan.project_id)
        self.assertEqual(report["blocked_queued"], [
            {"id": "leaf", "direct_unmet_ids": ["middle"], "frontier_ids": ["root"]},
            {"id": "middle", "direct_unmet_ids": ["root"], "frontier_ids": ["root"]},
        ])
        self.assertEqual(report["frontier"], [{
            "id": "root", "state": "queued", "worker_id": None, "task_id": None,
            "blocked_queued_ids": ["leaf", "middle"],
        }])

    def test_mixed_states_remain_distinct_and_follow_native_order(self):
        plan = plan_for(
            ("failed", ()), ("unknown", ()), ("active", ()), ("starting", ()),
            ("ready", ()), ("done", ()), ("bridge", ("unknown", "ready")),
            ("target", ("starting", "bridge", "active", "failed", "done")),
            ("unused", ()),
        )
        with Ledger() as ledger:
            ledger.record_plan(plan)
            for part_id, state in (
                ("failed", "failed"), ("unknown", "outcome_unknown"),
                ("active", "running"), ("starting", "dispatching"), ("done", "completed"),
            ):
                set_state(ledger, plan, part_id, state)
            report = inspect_blockers(ledger, plan.project_id)
        self.assertEqual(report["queued_ready_ids"], ["ready", "unused"])
        self.assertEqual(report["blocked_queued"], [
            {"id": "bridge", "direct_unmet_ids": ["unknown", "ready"],
             "frontier_ids": ["unknown", "ready"]},
            {"id": "target", "direct_unmet_ids": ["starting", "bridge", "active", "failed"],
             "frontier_ids": ["failed", "unknown", "active", "starting", "ready"]},
        ])
        self.assertEqual([(row["id"], row["state"], row["blocked_queued_ids"])
                          for row in report["frontier"]], [
            ("failed", "failed", ["target"]),
            ("unknown", "outcome_unknown", ["bridge", "target"]),
            ("active", "running", ["target"]),
            ("starting", "dispatching", ["target"]),
            ("ready", "queued", ["bridge", "target"]),
        ])
        self.assertEqual(report["frontier"][2]["task_id"], "task-active")
        self.assertEqual(report["frontier"][3]["worker_id"], "worker-starting")
        self.assertIsNone(report["frontier"][3]["task_id"])

    def test_shared_diamond_counts_each_downstream_part_once(self):
        plan = plan_for(
            ("target", ("right", "left")), ("left", ("root",)),
            ("root", ()), ("right", ("root",)),
        )
        with Ledger() as ledger:
            ledger.record_plan(plan)
            report = inspect_blockers(ledger, plan.project_id)
        self.assertEqual(report["frontier"][0]["blocked_queued_ids"],
                         ["target", "left", "right"])
        self.assertEqual(report["blocked_queued"][0]["direct_unmet_ids"], ["right", "left"])
        self.assertEqual(report["blocked_queued"][0]["frontier_ids"], ["root"])

    def test_completed_and_nonqueued_parts_cut_traversal(self):
        plan = plan_for(
            ("old", ()), ("finished", ("old",)), ("ready", ("finished",)),
            ("active", ("old",)), ("target", ("active",)),
        )
        with Ledger() as ledger:
            ledger.record_plan(plan)
            set_state(ledger, plan, "old", "failed")
            set_state(ledger, plan, "finished", "completed")
            set_state(ledger, plan, "active", "running")
            report = inspect_blockers(ledger, plan.project_id)
        self.assertEqual(report["queued_ready_ids"], ["ready"])
        self.assertEqual(report["blocked_queued"], [{
            "id": "target", "direct_unmet_ids": ["active"], "frontier_ids": ["active"],
        }])
        self.assertEqual([row["id"] for row in report["frontier"]], ["active"])

    def test_one_select_no_writes_and_detached_results(self):
        plan = plan_for(("root", ()), ("leaf", ("root",)))
        with Ledger() as ledger:
            ledger.record_plan(plan)
            before = list(ledger._db.iterdump())
            statements, denied = [], []
            allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}

            def authorize(action, *args):
                if action in allowed:
                    return sqlite3.SQLITE_OK
                denied.append(action)
                return sqlite3.SQLITE_DENY

            ledger._db.set_trace_callback(statements.append)
            ledger._db.set_authorizer(authorize)
            try:
                report = inspect_blockers(ledger, plan.project_id)
            finally:
                ledger._db.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
                ledger._db.set_trace_callback(None)
            self.assertEqual(denied, [])
            self.assertEqual(len(statements), 1)
            self.assertTrue(statements[0].lstrip().upper().startswith("SELECT"))
            self.assertEqual(list(ledger._db.iterdump()), before)
            report["frontier"][0]["blocked_queued_ids"].clear()
            report["queued_ready_ids"].clear()
            fresh = inspect_blockers(ledger, plan.project_id)
            self.assertEqual(fresh["frontier"][0]["blocked_queued_ids"], ["leaf"])
            self.assertEqual(fresh["queued_ready_ids"], ["root"])

    def test_later_completed_work_changes_only_a_later_observation(self):
        plan = plan_for(("root", ()), ("leaf", ("root",)))
        with Ledger() as ledger:
            ledger.record_plan(plan)
            before = inspect_blockers(ledger, plan.project_id)
            set_state(ledger, plan, "root", "completed")
            after = inspect_blockers(ledger, plan.project_id)
        self.assertEqual(before["frontier"][0]["id"], "root")
        self.assertEqual(after["frontier"], [])
        self.assertEqual(after["blocked_queued"], [])
        self.assertEqual(after["queued_ready_ids"], ["leaf"])

    def test_complete_native_validation_precedes_blocker_report(self):
        plan = plan_for(("root", ()), ("leaf", ("root",)), ("unrelated", ()))
        with Ledger() as ledger:
            ledger.record_plan(plan)
            ledger._db.execute("UPDATE parts SET payload_json='{}' WHERE part_id='unrelated'")
            with self.assertRaises(InspectionError) as error:
                inspect_blockers(ledger, plan.project_id)
            self.assertEqual(error.exception.code, "invalid_record")
            with self.assertRaises(InspectionError) as error:
                inspect_blockers(ledger, "unknown-project")
            self.assertEqual(error.exception.code, "project_not_found")

    def test_dependency_chain_can_exceed_python_recursion_limit(self):
        count = sys.getrecursionlimit() + 25
        entries = [
            ("p" + str(index), ("p" + str(index - 1),) if index else ())
            for index in reversed(range(count))
        ]
        plan = plan_for(*entries)
        with Ledger() as ledger:
            ledger.record_plan(plan)
            report = inspect_blockers(ledger, plan.project_id)
        self.assertEqual(len(report["blocked_queued"]), count - 1)
        self.assertEqual(report["frontier"][0]["id"], "p0")
        self.assertEqual(report["frontier"][0]["blocked_queued_ids"],
                         ["p" + str(index) for index in reversed(range(1, count))])


class BlockerCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fanout-blockers-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.database = self.root / "retained 東京 #1.sqlite3"
        self.plan = plan_for(("root", ()), ("leaf", ("root",)), project="project-cli")
        with Ledger(str(self.database)) as ledger:
            ledger.record_plan(self.plan)
            ledger.mark_dispatching(self.plan.project_id, "root", "worker-東京",
                                    {"model": "local-reference", "effort": "low"})
            ledger.mark_running(self.plan.project_id, "root", "task-é")

    def run_cli(self, *extra, project=None, database=None):
        return subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.blockers",
             "--database", str(database or self.database),
             "--project", project or self.plan.project_id, *map(str, extra)],
            cwd=REPO, capture_output=True, timeout=30,
        )

    def test_native_cli_utf8_report_and_new_output_preserve_database(self):
        before = self.database.read_bytes()
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["project_id"], "project-cli")
        self.assertEqual(report["frontier"][0]["blocked_queued_ids"], ["leaf"])
        self.assertEqual(report["frontier"][0]["worker_id"], "worker-東京")
        self.assertEqual(report["frontier"][0]["task_id"], "task-é")
        output = self.root / "blocker 東京 report.json"
        exported = self.run_cli("--output", output)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        self.assertEqual(exported.stdout, b"")
        self.assertEqual(output.read_bytes(), result.stdout)
        refused = self.run_cli("--output", output)
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(refused.stdout, b"")
        self.assertEqual(output.read_bytes(), result.stdout)
        self.assertEqual(self.database.read_bytes(), before)

    def test_missing_project_or_database_has_no_success_output(self):
        missing_project = self.run_cli(project="not-recorded")
        self.assertEqual(missing_project.returncode, 3)
        self.assertEqual(missing_project.stdout, b"")
        absent = self.root / "absent.sqlite3"
        missing_database = self.run_cli(database=absent)
        self.assertEqual(missing_database.returncode, 2)
        self.assertEqual(missing_database.stdout, b"")
        self.assertFalse(absent.exists())


if __name__ == "__main__":
    unittest.main()
