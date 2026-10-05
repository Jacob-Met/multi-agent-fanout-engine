import unittest

from fanout_engine import EffortRouter, Ledger, LedgerError, Plan, Route, dispatch_ready


class FakeHub:
    def __init__(self, fail_once=False):
        self.calls = []
        self.fail_once = fail_once

    def submit(self, part, *, route, worker_id, idempotency_key):
        self.calls.append((part.id, idempotency_key))
        if self.fail_once:
            self.fail_once = False
            raise TimeoutError("acceptance not observed")
        return {"task_id": "task-" + part.id}


class DispatchTests(unittest.TestCase):
    def setUp(self):
        self.plan = Plan.from_dict({
            "project": "dispatch-sample",
            "parts": [
                {"id": "prepare", "instruction": "Prepare the source set."},
                {"id": "review", "instruction": "Review the output.", "depends_on": ["prepare"]},
            ],
        })
        catalog = {"model-a": ("low", "high")}
        self.router = EffortRouter(catalog, pool=(Route("model-a", "low"),), step_up=Route("model-a", "high"))

    def test_dependency_and_completion_flow(self):
        with Ledger() as ledger:
            hub = FakeHub()
            report = dispatch_ready(self.plan, ledger, hub, self.router, worker_for=lambda _: "worker-a")
            self.assertEqual(report.started, ("prepare",))
            self.assertEqual(report.not_ready, ("review",))
            ledger.mark_completed("dispatch-sample", "prepare", "artifact://prepare")
            report = dispatch_ready(self.plan, ledger, hub, self.router, worker_for=lambda _: "worker-a")
            self.assertEqual(report.started, ("review",))
            self.assertEqual(ledger.part_state("dispatch-sample", "review"), "running")

    def test_unknown_submission_is_never_replayed(self):
        with Ledger() as ledger:
            hub = FakeHub(fail_once=True)
            first = dispatch_ready(self.plan, ledger, hub, self.router, worker_for=lambda _: "worker-a")
            self.assertEqual(first.outcome_unknown, ("prepare",))
            self.assertEqual(ledger.part_state("dispatch-sample", "prepare"), "outcome_unknown")
            second = dispatch_ready(self.plan, ledger, hub, self.router, worker_for=lambda _: "worker-a")
            self.assertEqual(second.started, ())
            self.assertEqual(len(hub.calls), 1)
            key = ledger.idempotency_key("dispatch-sample", "prepare")
            ledger.reconcile_unknown(
                "dispatch-sample", "prepare", verdict="failed",
                evidence={"source": "fake hub receipt", "locator": key, "finding": "no task was accepted"},
            )
            self.assertEqual(ledger.part_state("dispatch-sample", "prepare"), "failed")
            with self.assertRaises(LedgerError):
                ledger.mark_dispatching("dispatch-sample", "prepare", "worker-a", {"model": "model-a", "effort": "low"})

    def test_plan_conflict_is_rejected(self):
        with Ledger() as ledger:
            ledger.record_plan(self.plan)
            changed = Plan.from_dict({"project": "dispatch-sample", "parts": [
                {"id": "other", "instruction": "Different plan."},
            ]})
            with self.assertRaises(LedgerError):
                ledger.record_plan(changed)


if __name__ == "__main__":
    unittest.main()
