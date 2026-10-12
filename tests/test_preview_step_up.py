"""A preview must revalidate the step-up currently configured on a router."""
import unittest
from unittest.mock import patch

from fanout_engine import EffortRouter, Plan, Route
from fanout_engine.preview import preview_plan


class PreviewStepUpTests(unittest.TestCase):
    def setUp(self):
        self.plan = Plan.from_dict({"project": "step-up-preview", "parts": [
            {"id": "work", "instruction": "Preview an authored part."},
        ]})
        self.router = EffortRouter(
            {"model-a": ("low", "high"), "model-b": ("low",)},
            pool=(Route("model-a", "low"),),
            step_up=Route("model-a", "high"),
        )

    def test_replaced_model_outside_catalog_is_rejected(self):
        self.router.step_up = Route("outside-catalog", "high")
        with self.assertRaisesRegex(ValueError, "authorized catalog"):
            preview_plan(self.plan, self.router)

    def test_replaced_effort_outside_catalog_is_rejected(self):
        self.router.step_up = Route("model-b", "high")
        with self.assertRaisesRegex(ValueError, "effort is not authorized"):
            preview_plan(self.plan, self.router)

    def test_replaced_non_route_has_a_validation_error(self):
        self.router.step_up = {"model": "model-a", "effort": "high"}
        with self.assertRaisesRegex(ValueError, "native Route"):
            preview_plan(self.plan, self.router)

    def test_authorized_replacement_is_reported_without_performing_step_up(self):
        self.router.step_up = Route("model-b", "low")
        with patch.object(self.router, "step_up_after_refusal", side_effect=AssertionError("must not perform step-up")):
            report = preview_plan(self.plan, self.router)
        self.assertEqual(report["configured_step_up"], {"model": "model-b", "effort": "low"})
        self.assertEqual(report["routes"][0]["route"], {"model": "model-a", "effort": "low"})

    def test_same_route_remains_configuration_without_step_up_eligibility(self):
        self.router.step_up = self.router.pool[0]
        report = preview_plan(self.plan, self.router)
        self.assertEqual(report["configured_step_up"], {"model": "model-a", "effort": "low"})

    def test_removed_step_up_is_reported_as_null(self):
        self.router.step_up = None
        self.assertIsNone(preview_plan(self.plan, self.router)["configured_step_up"])


if __name__ == "__main__":
    unittest.main()
