"""Per-part eligibility stays fresh while adapter callbacks change the ledger."""
import unittest

from fanout_engine import EffortRouter, Ledger, LedgerError, Plan, Route, dispatch_ready


class CallbackHub:
    def __init__(self, callback=lambda part: None):
        self.callback = callback
        self.calls = []

    def submit(self, part, *, route, worker_id, idempotency_key):
        self.calls.append((part.id, route, worker_id, idempotency_key))
        self.callback(part)
        return {"task_id": "task-" + part.id}


class DispatchEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.plan = Plan.from_dict({
            "project": "fresh-eligibility",
            "parts": [
                {"id": "first", "instruction": "Run the local callback."},
                {"id": "later", "instruction": "Observe the callback's state."},
                {"id": "last", "instruction": "Still submit unrelated queued work."},
            ],
        })
        self.route = Route("fixture", "high")
        self.router = EffortRouter({"fixture": ("high",)}, pool=(self.route,))

    def test_adapter_callback_can_advance_a_later_part_to_any_nonqueued_state(self):
        for state in ("dispatching", "running", "outcome_unknown", "completed", "failed"):
            with self.subTest(state=state), Ledger() as ledger:
                ledger.record_plan(self.plan)
                retained = []

                def callback(part):
                    if part.id != "first":
                        return
                    project = self.plan.project_id
                    ledger.mark_dispatching(project, "later", "other-worker",
                                            {"model": "fixture", "effort": "high"})
                    if state in ("running", "completed"):
                        ledger.mark_running(project, "later", "other-task")
                    if state == "completed":
                        ledger.mark_completed(project, "later", "fixture:other-artifact")
                    if state in ("outcome_unknown", "failed"):
                        evidence = {"source": "local callback", "locator": "fixture:later",
                                    "finding": "Authored local state transition."}
                        ledger.mark_outcome_unknown(project, "later", evidence)
                        if state == "failed":
                            ledger.reconcile_unknown(project, "later", verdict="failed",
                                                     evidence=evidence)
                    retained.append(ledger.part(project, "later"))

                workers = []

                def worker_for(part):
                    workers.append(part.id)
                    return "this-worker"

                hub = CallbackHub(callback)
                report = dispatch_ready(self.plan, ledger, hub, self.router,
                                        worker_for=worker_for)
                self.assertEqual(report.started, ("first", "last"))
                self.assertEqual(report.outcome_unknown, ())
                self.assertEqual(report.not_ready, ())
                self.assertEqual(workers, ["first", "last"])
                self.assertEqual([call[0] for call in hub.calls], ["first", "last"])
                self.assertEqual(ledger.part(self.plan.project_id, "later"), retained[0])
                self.assertEqual(retained[0]["state"], state)
                for part_id, route, worker_id, key in hub.calls:
                    self.assertEqual(route, self.route)
                    self.assertEqual(worker_id, "this-worker")
                    self.assertEqual(key, self.plan.idempotency_key(part_id))

                again = dispatch_ready(self.plan, ledger, hub, self.router,
                                       worker_for=worker_for)
                self.assertEqual(again.started, ())
                self.assertEqual(len(hub.calls), 2)
                self.assertEqual(workers, ["first", "last"])

    def test_state_change_after_eligibility_read_keeps_transactional_admission_guard(self):
        with Ledger() as ledger:
            hub = CallbackHub()

            def worker_for(part):
                ledger.mark_dispatching(self.plan.project_id, part.id, "other-worker",
                                        {"model": "fixture", "effort": "high"})
                return "this-worker"

            with self.assertRaisesRegex(LedgerError, "only queued parts"):
                dispatch_ready(self.plan, ledger, hub, self.router, worker_for=worker_for)
            self.assertEqual(hub.calls, [])
            self.assertEqual(ledger.part_state(self.plan.project_id, "first"), "dispatching")
            self.assertEqual(ledger.part_state(self.plan.project_id, "later"), "queued")
            self.assertEqual(ledger.part_state(self.plan.project_id, "last"), "queued")
            self.assertEqual([e["event"] for e in ledger.events(self.plan.project_id)],
                             ["plan_recorded", "dispatch_started"])

    def test_missing_ready_row_surfaces_existing_ledger_error_without_submission(self):
        with Ledger() as ledger:
            ledger.record_plan(self.plan)
            ledger._db.execute("DELETE FROM parts WHERE project_id=? AND part_id=?",
                               (self.plan.project_id, "first"))
            events = ledger.events(self.plan.project_id)
            hub = CallbackHub()
            with self.assertRaisesRegex(LedgerError, "part is not in the ledger"):
                dispatch_ready(self.plan, ledger, hub, self.router,
                               worker_for=lambda part: "this-worker")
            self.assertEqual(hub.calls, [])
            self.assertEqual(ledger.events(self.plan.project_id), events)


if __name__ == "__main__":
    unittest.main()
