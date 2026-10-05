import unittest

from fanout_engine import Plan, PlanError, strict_json_loads


class PlanTests(unittest.TestCase):
    def test_ready_parts_and_stable_idempotency_key(self):
        plan = Plan.from_dict({
            "project": "sample-project",
            "parts": [
                {"id": "research", "instruction": "Collect public sources."},
                {"id": "draft", "instruction": "Write a summary.", "depends_on": ["research"]},
            ],
        })
        self.assertEqual([p.id for p in plan.ready_parts()], ["research"])
        self.assertEqual([p.id for p in plan.ready_parts({"research"})], ["research", "draft"])
        self.assertEqual(plan.idempotency_key("research"), plan.idempotency_key("research"))
        self.assertNotEqual(plan.idempotency_key("research"), plan.idempotency_key("draft"))

    def test_rejects_unknown_dependency_and_cycle(self):
        with self.assertRaises(PlanError):
            Plan.from_dict({"project": "sample", "parts": [
                {"id": "one", "instruction": "x", "depends_on": ["missing"]},
            ]})
        with self.assertRaises(PlanError):
            Plan.from_dict({"project": "sample", "parts": [
                {"id": "one", "instruction": "x", "depends_on": ["two"]},
                {"id": "two", "instruction": "y", "depends_on": ["one"]},
            ]})

    def test_strict_json_rejects_duplicate_keys_and_nan(self):
        with self.assertRaises(PlanError):
            strict_json_loads('{"project":"a","project":"b"}')
        with self.assertRaises(PlanError):
            strict_json_loads('{"effort":NaN}')


if __name__ == "__main__":
    unittest.main()
