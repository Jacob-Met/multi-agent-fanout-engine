"""Default route admission after a caller replaces the public pool."""
import unittest

from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready


class RoutingPoolRevalidationTests(unittest.TestCase):
    def router(self):
        return EffortRouter({"allowed": ("low", "high")},
                            pool=(Route("allowed", "low"),))

    def test_replaced_default_pool_refuses_unlisted_model_and_effort(self):
        for route in (Route("unlisted", "low"), Route("allowed", "max")):
            with self.subTest(route=route):
                router = self.router()
                router.pool = (route,)
                with self.assertRaises(ValueError):
                    router.route_for("part")

    def test_authorized_replacement_remains_available(self):
        router = self.router()
        selected = Route("allowed", "high")
        router.pool = (selected,)
        self.assertEqual(router.route_for("part"), selected)

    def test_explicit_selection_keeps_its_native_precedence_and_validation(self):
        router = self.router()
        router.pool = (Route("unlisted", "low"),)
        selected = Route("allowed", "high")
        self.assertEqual(router.route_for("part", selected), selected)
        with self.assertRaises(ValueError):
            router.route_for("part", Route("allowed", "max"))

    def test_refused_dispatch_stays_queued_then_uses_the_same_key(self):
        for suffix, route in (("model", Route("unlisted", "low")),
                              ("effort", Route("allowed", "max"))):
            with self.subTest(route=route):
                router = self.router()
                router.pool = (route,)
                plan = Plan.from_dict({"project": "pool-" + suffix, "parts": [
                    {"id": "part", "instruction": "Authored local receiving fixture."}
                ]})

                class CapturingHub:
                    def __init__(self):
                        self.calls = []

                    def submit(self, part, *, route, worker_id, idempotency_key):
                        self.calls.append((part.id, route, worker_id, idempotency_key))
                        return {"task_id": "authored-task"}

                hub = CapturingHub()
                with Ledger(":memory:") as ledger:
                    with self.assertRaises(ValueError):
                        dispatch_ready(plan, ledger, hub, router,
                                       worker_for=lambda part: "authored-worker")
                    self.assertEqual(hub.calls, [])
                    self.assertEqual(ledger.part_state(plan.project_id, "part"), "queued")
                    self.assertEqual([event["event"] for event in ledger.events(plan.project_id)],
                                     ["plan_recorded"])
                    key = ledger.idempotency_key(plan.project_id, "part")
                    router.pool = (Route("allowed", "high"),)
                    report = dispatch_ready(plan, ledger, hub, router,
                                            worker_for=lambda part: "authored-worker")
                    self.assertEqual(report.started, ("part",))
                    self.assertEqual(report.outcome_unknown, ())
                    self.assertEqual(hub.calls, [("part", Route("allowed", "high"),
                                                 "authored-worker", key)])
                    self.assertEqual(ledger.part_state(plan.project_id, "part"), "running")
                    self.assertEqual([event["event"] for event in ledger.events(plan.project_id)],
                                     ["plan_recorded", "dispatch_started", "dispatch_accepted"])


if __name__ == "__main__":
    unittest.main()
