import unittest

from fanout_engine import EffortRouter, Route, UnsafeStepUp


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {"model-a": ("low", "high"), "model-b": ("low", "high")}
        self.low_a = Route("model-a", "low")
        self.low_b = Route("model-b", "low")
        self.high_b = Route("model-b", "high")
        self.router = EffortRouter(self.catalog, pool=(self.low_a, self.low_b), step_up=self.high_b)

    def test_pool_choice_is_stable_and_explicit_route_wins(self):
        self.assertEqual(self.router.route_for("part-1"), self.router.route_for("part-1"))
        self.assertEqual(self.router.route_for("part-1", self.high_b), self.high_b)

    def test_rejects_route_outside_authorized_catalog(self):
        with self.assertRaises(ValueError):
            EffortRouter(self.catalog, pool=(Route("model-a", "max"),))
        with self.assertRaises(ValueError):
            self.router.route_for("part-1", Route("model-c", "low"))

    def test_step_up_only_before_output_and_effect(self):
        self.assertEqual(self.router.step_up_after_refusal(self.low_a, refusal_before_output=True), self.high_b)
        with self.assertRaises(UnsafeStepUp):
            self.router.step_up_after_refusal(self.low_a, refusal_before_output=False)
        with self.assertRaises(UnsafeStepUp):
            self.router.step_up_after_refusal(self.low_a, refusal_before_output=True, output_received=True)
        with self.assertRaises(UnsafeStepUp):
            self.router.step_up_after_refusal(self.low_a, refusal_before_output=True, effect_started=True)


if __name__ == "__main__":
    unittest.main()
