"""Public strict_json_loads finite-number contract tests.

Authored source only; no import, fixture calibration, or test has been run.
A future admitted receiver must use the real package and standard library.
Overflow/underflow applicability is calibrated there, not assumed universal.
"""
import json
import math
import unittest

from fanout_engine import PlanError, strict_json_loads


class StrictJsonFiniteNumberTests(unittest.TestCase):
    def assert_rejected(self, document, diagnostic):
        with self.assertRaises(PlanError) as raised:
            strict_json_loads(document)
        self.assertEqual(str(raised.exception), diagnostic)

    def test_overflow_is_refused_at_root_and_inside_containers(self):
        cases = (
            ("root-positive", "1e10000", "1e10000"),
            ("root-negative", "-1e10000", "-1e10000"),
            ("array-positive", "1e10000", '[0, [1e10000], "kept"]'),
            ("array-negative", "-1e10000", '[0, [-1e10000], "kept"]'),
            ("object-positive", "1e10000", '{"outer": {"value": 1e10000}}'),
            ("object-negative", "-1e10000", '{"outer": {"value": -1e10000}}'),
        )
        for label, token, document in cases:
            with self.subTest(case=label):
                # Runtime fixture admission only. An inapplicable token is not
                # counted as evidence that the public helper refuses overflow.
                try:
                    ordinary = float(token)
                except (OverflowError, ValueError) as exc:
                    self.skipTest("ordinary float conversion is unsupported: " + type(exc).__name__)
                if not math.isinf(ordinary):
                    self.skipTest("the authored token does not overflow to infinity on this receiver")
                self.assert_rejected(document, "non-finite JSON number")

    def test_named_nonfinite_constants_keep_their_diagnostic(self):
        cases = (
            "NaN",
            "Infinity",
            "-Infinity",
            '{"value": NaN}',
            "[Infinity]",
            '{"outer": [-Infinity]}',
        )
        for document in cases:
            with self.subTest(document=document):
                self.assert_rejected(document, "non-finite JSON number")

    def test_duplicate_keys_keep_their_diagnostic(self):
        cases = (
            '{"a": 1, "a": 2}',
            '{"outer": {"x": 1, "x": 2}}',
            '[{"x": 1, "x": 2}]',
        )
        for document in cases:
            with self.subTest(document=document):
                self.assert_rejected(document, "duplicate JSON object key")

    def test_invalid_json_and_input_types_keep_their_diagnostic(self):
        cases = (
            ("empty", ""),
            ("object-value-missing", '{"x":}'),
            ("trailing-comma", "[1,]"),
            ("extra-document", "true false"),
            ("none-input", None),
            ("integer-input", 7),
            ("list-input", []),
        )
        for label, document in cases:
            with self.subTest(case=label):
                self.assert_rejected(document, "invalid JSON document")

    def test_finite_values_builtin_types_and_object_order_are_preserved(self):
        scalar_documents = (
            "1.25",
            "-2.5e2",
            "0.1",
            "0",
            "1234567890123456789012345678901234567890",
            "true",
            "false",
            "null",
        )
        for document in scalar_documents:
            with self.subTest(document=document):
                expected = json.loads(document)
                actual = strict_json_loads(document)
                self.assertEqual(actual, expected)
                self.assertIs(type(actual), type(expected))
                if type(expected) is float:
                    self.assertTrue(math.isfinite(actual))

        document = (
            '{"z": [1, 2.5, true, null, {"b": "1e10000", "a": false}], '
            '"a": {}, "m": []}'
        )
        actual = strict_json_loads(document)
        self.assertEqual(actual, json.loads(document))
        self.assertIs(type(actual), dict)
        self.assertEqual(list(actual), ["z", "a", "m"])
        self.assertIs(type(actual["z"]), list)
        self.assertIs(type(actual["a"]), dict)
        self.assertIs(type(actual["m"]), list)
        for item, expected_type in zip(actual["z"], (int, float, bool, type(None), dict)):
            self.assertIs(type(item), expected_type)
        self.assertEqual(list(actual["z"][4]), ["b", "a"])
        self.assertIs(type(actual["z"][4]["b"]), str)
        self.assertIs(type(actual["z"][4]["a"]), bool)

    def test_negative_zero_keeps_ordinary_float_sign(self):
        for document in ("-0.0", "-0e0", "-0.000e+10"):
            with self.subTest(document=document):
                expected = json.loads(document)
                actual = strict_json_loads(document)
                self.assertIs(type(actual), float)
                self.assertEqual(actual, expected)
                self.assertEqual(actual, 0.0)
                self.assertEqual(math.copysign(1.0, actual), math.copysign(1.0, expected))

    def test_finite_underflow_keeps_ordinary_value_and_sign(self):
        for token in ("1e-10000", "-1e-10000"):
            with self.subTest(token=token):
                try:
                    expected = float(token)
                except (OverflowError, ValueError) as exc:
                    self.skipTest("ordinary float conversion is unsupported: " + type(exc).__name__)
                if not math.isfinite(expected) or expected != 0.0:
                    self.skipTest("the authored token is not a finite underflow-to-zero control here")
                actual = strict_json_loads(token)
                self.assertIs(type(actual), float)
                self.assertTrue(math.isfinite(actual))
                self.assertEqual(actual, expected)
                self.assertEqual(math.copysign(1.0, actual), math.copysign(1.0, expected))

    def test_numeric_looking_strings_and_escaped_surrogates_stay_strings(self):
        document = '["1e10000", "-1e10000", "NaN", "Infinity", "-Infinity"]'
        actual = strict_json_loads(document)
        self.assertEqual(actual, ["1e10000", "-1e10000", "NaN", "Infinity", "-Infinity"])
        self.assertIs(type(actual), list)
        for item in actual:
            self.assertIs(type(item), str)

        # Do not encode these decoded values as UTF-8: that would impose a new
        # admission policy instead of preserving the ordinary JSON decoder.
        for document in (r'"\ud800"', r'{"text": "\udfff"}'):
            with self.subTest(document=document):
                expected = json.loads(document)
                actual = strict_json_loads(document)
                self.assertEqual(actual, expected)
                self.assertIs(type(actual), type(expected))
                if type(actual) is dict:
                    self.assertIs(type(actual["text"]), str)
                else:
                    self.assertIs(type(actual), str)


if __name__ == "__main__":
    unittest.main()
