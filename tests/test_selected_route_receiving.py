"""Independent native SQLite receiving for selected default-route validation.

The frozen driver imports either retained original or candidate via PYTHONPATH.
Every Hub is a local recording adapter and every SQLite database is temporary.
It exercises selected-route authority and partial-batch continuation without
changing dispatch, preview, inspection, failure transitions, or catalog rules.
"""
import tempfile
from pathlib import Path
import unittest

from fanout_engine import EffortRouter, Ledger, Part, Plan, Route, dispatch_ready


class RecordingHub:
    def __init__(self, uncertain_first=False):
        self.calls = []
        self.uncertain_first = uncertain_first

    def submit(self, part, *, route, worker_id, idempotency_key):
        self.calls.append({
            "part": part.id, "route": route, "worker": worker_id,
            "key": idempotency_key,
        })
        if self.uncertain_first and part.id == "alpha":
            raise ConnectionError("fixture accepted effect before acknowledgement loss")
        return {"task_id": "fixture-task-" + part.id}


class SelectedRouteReceiving(unittest.TestCase):
    def router(self):
        catalog = {"model-a": ["low", "high"], "model-b": ["low"]}
        route_a, route_b = Route("model-a", "low"), Route("model-b", "low")
        return catalog, EffortRouter(catalog, pool=(route_a, route_b)), route_a, route_b

    def test_new_external_catalog_entry_does_not_authorize_a_replaced_default_pool(self):
        catalog, router, _, _ = self.router()
        catalog["model-c"] = ["high"]
        router.pool = (Route("model-c", "high"),)
        with self.assertRaisesRegex(ValueError, "authorized catalog"):
            router.route_for("alpha")

    def test_replaced_unauthorized_effort_refuses_before_hub_and_dispatch_transition(self):
        catalog, router, _, _ = self.router()
        catalog["model-b"].append("high")
        router.pool = (Route("model-b", "high"),)
        plan = Plan("effort-check", (Part("alpha", "Use one local fixture."),))
        hub, workers = RecordingHub(), []
        def worker_for(part):
            workers.append(part.id)
            return "fixture-worker"
        with tempfile.TemporaryDirectory() as temporary:
            path = str(Path(temporary) / "ledger.sqlite")
            with Ledger(path) as ledger:
                with self.assertRaisesRegex(ValueError, "effort is not authorized"):
                    dispatch_ready(plan, ledger, hub, router, worker_for=worker_for)
                row = ledger.part(plan.project_id, "alpha")
                self.assertEqual(row["state"], "queued")
                for field in ("worker_id", "task_id", "route_json"):
                    self.assertIsNone(row[field])
                self.assertEqual(row["idempotency_key"], plan.idempotency_key("alpha"))
                self.assertEqual([event["event"] for event in ledger.events(plan.project_id)],
                                 ["plan_recorded"])
            with Ledger(path) as reopened:
                self.assertEqual(reopened.part_state(plan.project_id, "alpha"), "queued")
        self.assertEqual(hub.calls, [])
        # Existing ordering is explicit: caller selection can occur before route validation.
        self.assertEqual(workers, ["alpha"])

    def receive_partial_batch(self, uncertain_first):
        _, router, route_a, _ = self.router()
        # Stable known choices for this two-entry pool: alpha -> 0, beta -> 1.
        router.pool = (route_a, Route("model-outside-catalog", "low"))
        plan = Plan("partial-" + ("unknown" if uncertain_first else "accepted"), (
            Part("alpha", "First local fixture."),
            Part("beta", "Second local fixture."),
            Part("tail", "Third local fixture."),
        ))
        hub, workers = RecordingHub(uncertain_first=uncertain_first), []
        def worker_for(part):
            workers.append(part.id)
            return "fixture-worker"
        with tempfile.TemporaryDirectory() as temporary:
            path = str(Path(temporary) / "ledger.sqlite")
            with Ledger(path) as ledger:
                with self.assertRaisesRegex(ValueError, "authorized catalog"):
                    dispatch_ready(plan, ledger, hub, router, worker_for=worker_for)
                first_state = "outcome_unknown" if uncertain_first else "running"
                self.assertEqual(ledger.part_state(plan.project_id, "alpha"), first_state)
                self.assertEqual(ledger.part_state(plan.project_id, "beta"), "queued")
                self.assertEqual(ledger.part_state(plan.project_id, "tail"), "queued")
                self.assertEqual([call["part"] for call in hub.calls], ["alpha"])
                self.assertEqual(workers, ["alpha", "beta"])
                self.assertEqual(ledger.events(plan.project_id, "beta"), [])
                self.assertEqual(ledger.events(plan.project_id, "tail"), [])
                alpha_before = ledger.part(plan.project_id, "alpha")
                alpha_events = ledger.events(plan.project_id, "alpha")
                self.assertEqual([event["event"] for event in alpha_events],
                                 ["dispatch_started",
                                  "outcome_unknown" if uncertain_first else "dispatch_accepted"])
            # Reopen actual persisted SQLite before continuing the queued remainder.
            router.pool = (route_a,)
            with Ledger(path) as ledger:
                report = dispatch_ready(plan, ledger, hub, router, worker_for=worker_for)
                self.assertEqual(report.started, ("beta", "tail"))
                self.assertEqual(report.outcome_unknown, ())
                self.assertEqual(report.not_ready, ())
                self.assertEqual(ledger.part(plan.project_id, "alpha"), alpha_before)
                self.assertEqual(ledger.events(plan.project_id, "alpha"), alpha_events)
                self.assertEqual(ledger.part_state(plan.project_id, "beta"), "running")
                self.assertEqual(ledger.part_state(plan.project_id, "tail"), "running")
                self.assertEqual([event["event"] for event in ledger.events(plan.project_id)].count(
                    "plan_recorded"), 1)
        self.assertEqual([call["part"] for call in hub.calls], ["alpha", "beta", "tail"])
        for call in hub.calls:
            self.assertEqual(call["key"], plan.idempotency_key(call["part"]))
            self.assertEqual(call["route"], route_a)
        self.assertEqual(workers, ["alpha", "beta", "beta", "tail"])

    def test_earlier_accepted_part_survives_later_refusal_and_is_not_replayed(self):
        self.receive_partial_batch(uncertain_first=False)

    def test_earlier_unknown_effect_stays_parked_when_later_queued_work_resumes(self):
        self.receive_partial_batch(uncertain_first=True)

    def test_valid_explicit_route_retains_precedence_over_invalid_default_pool(self):
        _, router, _, route_b = self.router()
        router.pool = (Route("model-outside-catalog", "high"),)
        plan = Plan("explicit-check", (Part("beta", "Explicit local fixture."),))
        hub = RecordingHub()
        with Ledger() as ledger:
            report = dispatch_ready(
                plan, ledger, hub, router, worker_for=lambda _: "fixture-worker",
                explicit_routes={"beta": route_b})
            self.assertEqual(report.started, ("beta",))
            self.assertEqual(ledger.part(plan.project_id, "beta")["route"],
                             {"model": "model-b", "effort": "low"})
        self.assertEqual(len(hub.calls), 1)
        self.assertEqual(hub.calls[0]["route"], route_b)

    def test_unselected_invalid_neighbor_does_not_change_a_valid_deterministic_choice(self):
        _, router, route_a, route_b = self.router()
        self.assertEqual(router.route_for("alpha"), route_a)
        self.assertEqual(router.route_for("beta"), route_b)
        router.pool = (route_a, Route("model-outside-catalog", "low"))
        for _ in range(3):
            self.assertEqual(router.route_for("alpha"), route_a)

    def test_inflight_and_dependency_blocked_parts_do_not_consult_the_invalid_pool(self):
        _, router, route_a, _ = self.router()
        router.pool = (Route("model-outside-catalog", "low"),)
        plan = Plan("readiness-check", (
            Part("alpha", "Already in flight."),
            Part("beta", "Wait for alpha.", depends_on=("alpha",)),
        ))
        hub = RecordingHub()
        def unexpected_worker(_):
            raise AssertionError("No eligible queued part should select a worker.")
        with Ledger() as ledger:
            ledger.record_plan(plan)
            ledger.mark_dispatching(plan.project_id, "alpha", "fixture-worker",
                                    {"model": route_a.model, "effort": route_a.effort})
            ledger.mark_running(plan.project_id, "alpha", "existing-fixture-task")
            before = ledger.events(plan.project_id)
            report = dispatch_ready(plan, ledger, hub, router, worker_for=unexpected_worker)
            self.assertEqual(report.started, ())
            self.assertEqual(report.outcome_unknown, ())
            self.assertEqual(report.not_ready, ("beta",))
            self.assertEqual(ledger.events(plan.project_id), before)
            self.assertEqual(ledger.part_state(plan.project_id, "beta"), "queued")
        self.assertEqual(hub.calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
