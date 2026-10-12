"""Reject malformed UTF-8 plan instructions through the native validation API."""
import unittest

from fanout_engine.plan import Part, Plan, PlanError


class PlanUtf8Tests(unittest.TestCase):
    def test_from_dict_rejects_unpaired_surrogates_as_plan_errors(self):
        for codepoint in (0xD800, 0xDFFF):
            with self.subTest(codepoint=codepoint):
                raw = {
                    "project": "utf8-check",
                    "parts": [{"id": "one", "instruction": "before" + chr(codepoint)}],
                }
                with self.assertRaisesRegex(PlanError, "UTF-8"):
                    Plan.from_dict(raw)

    def test_direct_constructor_uses_the_same_validation_boundary(self):
        part = Part("one", "after" + chr(0xD800))
        with self.assertRaisesRegex(PlanError, "UTF-8"):
            Plan("utf8-check", (part,))

    def test_valid_multilingual_instructions_retain_stable_digest_and_keys(self):
        content = "Résumé — Zürich — 漢字 — 😀"
        raw = {"project": "utf8-check", "parts": [{"id": "one", "instruction": content}]}
        first = Plan.from_dict(raw)
        second = Plan.from_dict(first.to_dict())
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.idempotency_key("one"), second.idempotency_key("one"))
        self.assertEqual(first.parts[0].instruction, content)


if __name__ == "__main__":
    unittest.main()
