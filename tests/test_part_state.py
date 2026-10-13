"""State-only consumers retain current state, project scope, and diagnostics."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fanout_engine import EffortRouter, Ledger, LedgerError, Plan, Route, dispatch_ready


ROUTE = {"model": "local-model", "effort": "low"}
EVIDENCE = {"source": "local receiving", "locator": "fixture:retained-evidence",
            "finding": "Retained Unicode evidence π. " * 10000}


def plan_for(project, names):
    return Plan.from_dict({"project": project, "parts": [
        {"id": name, "instruction": "Local work."} for name in names
    ]})


class PartStateTests(unittest.TestCase):
    def test_reopened_states_keep_large_evidence_and_observe_other_connection(self):
        names = ("queued", "dispatching", "running", "outcome_unknown", "completed", "failed")
        plan = plan_for("retained", names)
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "retained.sqlite")
            with Ledger(path) as ledger:
                ledger.record_plan(plan)
                for name in names[1:]:
                    ledger.mark_dispatching(plan.project_id, name, "local-worker", ROUTE)
                for name in ("running", "completed"):
                    ledger.mark_running(plan.project_id, name, "task-" + name)
                ledger.mark_completed(plan.project_id, "completed", "artifact:completed", EVIDENCE)
                for name in ("outcome_unknown", "failed"):
                    ledger.mark_outcome_unknown(plan.project_id, name, EVIDENCE)
                ledger.reconcile_unknown(plan.project_id, "failed", verdict="failed", evidence=EVIDENCE)
                snapshot = ledger.project_snapshot(plan.project_id)
                events = ledger.events(plan.project_id)

            with Ledger(path) as ledger, Ledger(path) as other:
                self.assertEqual({name: ledger.part_state(plan.project_id, name) for name in names},
                                 {name: name for name in names})
                self.assertEqual(ledger.project_snapshot(plan.project_id), snapshot)
                self.assertEqual(ledger.events(plan.project_id), events)
                self.assertEqual(ledger.part(plan.project_id, "completed")["evidence"], EVIDENCE)
                other.mark_dispatching(plan.project_id, "queued", "other-worker", ROUTE)
                self.assertEqual(ledger.part_state(plan.project_id, "queued"), "dispatching")

    def test_state_lookup_preserves_project_scope_and_missing_row_diagnostic(self):
        with Ledger() as ledger:
            ledger.record_plan(plan_for("first", ("shared", "only_first")))
            ledger.record_plan(plan_for("second", ("shared",)))
            ledger.mark_dispatching("first", "shared", "local-worker", ROUTE)
            self.assertEqual(ledger.part_state("first", "shared"), "dispatching")
            self.assertEqual(ledger.part_state("second", "shared"), "queued")
            for project, part in (("second", "only_first"), ("missing", "shared"), ("first", "missing")):
                with self.subTest(project=project, part=part):
                    with self.assertRaisesRegex(LedgerError, "^part is not in the ledger$"):
                        ledger.part_state(project, part)

    def test_dispatch_preserves_missing_row_failure_before_later_submissions(self):
        plan = plan_for("missing-row", ("first", "missing", "later"))
        router = EffortRouter({"local-model": ("low",)}, pool=(Route("local-model", "low"),))

        class Hub:
            def __init__(self):
                self.calls = []

            def submit(self, part, **kwargs):
                self.calls.append(part.id)
                return {"task_id": "task-" + part.id}

        with Ledger() as ledger:
            ledger.record_plan(plan)
            ledger._db.execute("DELETE FROM parts WHERE project_id=? AND part_id=?",
                               (plan.project_id, "missing"))
            hub = Hub()
            with self.assertRaisesRegex(LedgerError, "^part is not in the ledger$"):
                dispatch_ready(plan, ledger, hub, router, worker_for=lambda part: "local-worker")
            self.assertEqual(hub.calls, ["first"])
            self.assertEqual(ledger.part_state(plan.project_id, "first"), "running")
            self.assertEqual(ledger.part_state(plan.project_id, "later"), "queued")


if __name__ == "__main__":
    unittest.main()
