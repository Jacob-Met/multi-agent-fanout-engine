"""Receiving tests for fresh, per-part dispatch eligibility on a saved ledger."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fanout_engine import EffortRouter, Ledger, LedgerError, Plan, Route, dispatch_ready


ROUTE = {"model": "model-a", "effort": "low"}
EVIDENCE = {"source": "local fixture", "locator": "fixture:receipt", "finding": "observed"}


def plan_with(*parts):
    return Plan.from_dict({"project": "eligibility", "parts": [
        {"id": part_id, "instruction": "Local receiving fixture.", "depends_on": list(deps)}
        for part_id, deps in parts
    ]})


class RecordingHub:
    def __init__(self, before_return=None, ambiguous=()):
        self.calls = []
        self.before_return = before_return
        self.ambiguous = set(ambiguous)

    def submit(self, part, *, route, worker_id, idempotency_key):
        self.calls.append((part.id, route, worker_id, idempotency_key))
        if self.before_return is not None:
            self.before_return(part)
        if part.id in self.ambiguous:
            raise TimeoutError("Local fixture could not verify acceptance.")
        return {"task_id": "local-" + part.id}


class DispatchEligibilityTests(unittest.TestCase):
    def setUp(self):
        self.router = EffortRouter({"model-a": ("low",)}, pool=(Route("model-a", "low"),))

    def dispatch(self, plan, ledger, hub, worker_for=lambda part: "local-worker"):
        return dispatch_ready(plan, ledger, hub, self.router, worker_for=worker_for)

    def test_reopened_mixed_states_preserve_order_dependencies_and_no_replay(self):
        plan = plan_with(
            ("done", ()), ("running", ()), ("unknown", ()), ("failed", ()),
            ("dispatching", ()), ("ready", ()), ("ambiguous", ()),
            ("after_done", ("done",)), ("after_running", ("running",)),
            ("after_unknown", ("unknown",)), ("after_failed", ("failed",)),
            ("after_dispatching", ("dispatching",)), ("after_ready", ("ready",)),
        )
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "ledger.sqlite")
            with Ledger(path) as ledger:
                ledger.record_plan(plan)
                for part_id in ("done", "running", "unknown", "failed", "dispatching"):
                    ledger.mark_dispatching(plan.project_id, part_id, "earlier-worker", ROUTE)
                for part_id in ("done", "running"):
                    ledger.mark_running(plan.project_id, part_id, "earlier-" + part_id)
                ledger.mark_completed(plan.project_id, "done", "artifact:done", EVIDENCE)
                for part_id in ("unknown", "failed"):
                    ledger.mark_outcome_unknown(plan.project_id, part_id, EVIDENCE)
                ledger.reconcile_unknown(plan.project_id, "failed", verdict="failed", evidence=EVIDENCE)
                preserved = {part_id: ledger.part(plan.project_id, part_id)
                             for part_id in ("done", "running", "unknown", "failed", "dispatching")}

            hub = RecordingHub(ambiguous=("ambiguous",))
            with Ledger(path) as ledger:
                report = self.dispatch(plan, ledger, hub)
                self.assertEqual(report.started, ("ready", "after_done"))
                self.assertEqual(report.outcome_unknown, ("ambiguous",))
                self.assertEqual(report.not_ready, ("after_running", "after_unknown", "after_failed",
                                                   "after_dispatching", "after_ready"))
                self.assertEqual([call[0] for call in hub.calls], ["ready", "ambiguous", "after_done"])
                for part_id, route, worker_id, key in hub.calls:
                    self.assertEqual((route, worker_id, key),
                                     (Route("model-a", "low"), "local-worker", plan.idempotency_key(part_id)))
                for part_id, original in preserved.items():
                    self.assertEqual(ledger.part(plan.project_id, part_id), original)
                before_second = ledger.project_snapshot(plan.project_id)
                events_before_second = ledger.events(plan.project_id)

            with Ledger(path) as ledger:
                second = self.dispatch(plan, ledger, hub)
                self.assertEqual(second.started, ())
                self.assertEqual(second.outcome_unknown, ())
                self.assertEqual(second.not_ready, report.not_ready)
                self.assertEqual(len(hub.calls), 3)
                self.assertEqual(ledger.project_snapshot(plan.project_id), before_second)
                self.assertEqual(ledger.events(plan.project_id), events_before_second)

    def test_another_connection_can_claim_a_later_candidate_during_submit(self):
        plan = plan_with(("first", ()), ("claimed_elsewhere", ()), ("last", ()))
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "ledger.sqlite")
            with Ledger(path) as ledger, Ledger(path) as other:
                def accept_and_claim(part):
                    if part.id == "first":
                        other.mark_dispatching(plan.project_id, "claimed_elsewhere", "other-worker", ROUTE)
                        other.mark_running(plan.project_id, "claimed_elsewhere", "other-task")

                hub = RecordingHub(before_return=accept_and_claim)
                report = self.dispatch(plan, ledger, hub)
                self.assertEqual(report.started, ("first", "last"))
                self.assertEqual(report.outcome_unknown, ())
                self.assertEqual(report.not_ready, ())
                self.assertEqual([call[0] for call in hub.calls], ["first", "last"])
                retained = ledger.part(plan.project_id, "claimed_elsewhere")
                self.assertEqual((retained["state"], retained["worker_id"], retained["task_id"]),
                                 ("running", "other-worker", "other-task"))

            with Ledger(path) as ledger:
                self.assertEqual(self.dispatch(plan, ledger, hub).started, ())
                self.assertEqual(len(hub.calls), 2)

    def test_atomic_admission_still_refuses_a_claim_after_the_state_read(self):
        plan = plan_with(("raced", ()), ("later", ()))
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "ledger.sqlite")
            with Ledger(path) as ledger, Ledger(path) as other:
                def claim_before_admission(part):
                    other.mark_dispatching(plan.project_id, part.id, "other-worker", ROUTE)
                    return "local-worker"

                hub = RecordingHub()
                with self.assertRaisesRegex(LedgerError, "only queued parts may be dispatched"):
                    self.dispatch(plan, ledger, hub, worker_for=claim_before_admission)
                self.assertEqual(hub.calls, [])
                raced = ledger.part(plan.project_id, "raced")
                self.assertEqual((raced["state"], raced["worker_id"]), ("dispatching", "other-worker"))
                self.assertEqual(ledger.part_state(plan.project_id, "later"), "queued")

            with Ledger(path) as ledger:
                self.assertEqual(ledger.part_state(plan.project_id, "raced"), "dispatching")
                self.assertEqual(ledger.mark_interrupted_dispatches_unknown(plan.project_id), 1)
                report = self.dispatch(plan, ledger, hub)
                self.assertEqual(report.started, ("later",))
                self.assertEqual([call[0] for call in hub.calls], ["later"])
                self.assertEqual(ledger.part_state(plan.project_id, "raced"), "outcome_unknown")

    def test_completions_during_submit_only_unlock_dependencies_on_the_next_pass(self):
        plan = plan_with(("first", ()), ("after_first", ("first",)), ("last", ()))
        with TemporaryDirectory() as directory:
            path = str(Path(directory) / "ledger.sqlite")
            with Ledger(path) as ledger, Ledger(path) as other:
                def complete_first_when_last_is_submitted(part):
                    if part.id == "last":
                        other.mark_completed(plan.project_id, "first", "artifact:first", EVIDENCE)

                hub = RecordingHub(before_return=complete_first_when_last_is_submitted)
                first = self.dispatch(plan, ledger, hub)
                self.assertEqual(first.started, ("first", "last"))
                self.assertEqual(first.not_ready, ("after_first",))
                second = self.dispatch(plan, ledger, hub)
                self.assertEqual(second.started, ("after_first",))
                self.assertEqual(second.not_ready, ())
                self.assertEqual([call[0] for call in hub.calls], ["first", "last", "after_first"])


if __name__ == "__main__":
    unittest.main()
