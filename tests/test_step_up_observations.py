"""Step-up requires Boolean observations, without truthiness coercion."""
import itertools
import json
import unittest

from fanout_engine import EffortRouter, Route, UnsafeStepUp


class StepUpObservationTests(unittest.TestCase):
    def setUp(self):
        self.current = Route("allowed", "low")
        self.fallback = Route("allowed", "high")
        self.router = EffortRouter(
            {"allowed": ("low", "high")}, pool=(self.current,),
            step_up=self.fallback,
        )

    def test_all_boolean_combinations_keep_native_eligibility(self):
        for refusal, output, effect in itertools.product((False, True), repeat=3):
            with self.subTest(refusal=refusal, output=output, effect=effect):
                kwargs = {"refusal_before_output": refusal,
                          "output_received": output, "effect_started": effect}
                if (refusal, output, effect) == (True, False, False):
                    self.assertIs(
                        self.router.step_up_after_refusal(self.current, **kwargs),
                        self.fallback,
                    )
                else:
                    with self.assertRaises(UnsafeStepUp):
                        self.router.step_up_after_refusal(self.current, **kwargs)

    def test_existing_optional_observation_defaults_remain_available(self):
        self.assertIs(
            self.router.step_up_after_refusal(self.current, refusal_before_output=True),
            self.fallback,
        )

    def test_non_boolean_observations_refuse_for_every_field(self):
        invalid = (None, 0, 1, 0.0, 1.0, "", "false", "true", [], [False], {},
                   {"reported": False}, ())
        for field in ("refusal_before_output", "output_received", "effect_started"):
            for value in invalid:
                with self.subTest(field=field, value=value):
                    kwargs = {"refusal_before_output": True,
                              "output_received": False, "effect_started": False}
                    kwargs[field] = value
                    with self.assertRaises(UnsafeStepUp):
                        self.router.step_up_after_refusal(self.current, **kwargs)

    def test_json_unknowns_and_string_false_do_not_authorize_fallback(self):
        for document in (
            '{"refusal_before_output":"false"}',
            '{"refusal_before_output":true,"output_received":null}',
            '{"refusal_before_output":true,"effect_started":null}',
        ):
            with self.subTest(document=document):
                with self.assertRaises(UnsafeStepUp):
                    self.router.step_up_after_refusal(self.current, **json.loads(document))

    def test_invalid_observations_do_not_invoke_user_truthiness(self):
        class Observation:
            def __bool__(self):
                raise AssertionError("observation truthiness was invoked")

        for field in ("refusal_before_output", "output_received", "effect_started"):
            with self.subTest(field=field):
                kwargs = {"refusal_before_output": True,
                          "output_received": False, "effect_started": False}
                kwargs[field] = Observation()
                with self.assertRaises(UnsafeStepUp):
                    self.router.step_up_after_refusal(self.current, **kwargs)


if __name__ == "__main__":
    unittest.main()
