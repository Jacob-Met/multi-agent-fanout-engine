"""Bound native key lookup work while preserving mixed mutable membership."""
import hashlib
import unittest
from unittest.mock import patch

from fanout_engine.plan import Part, Plan, PlanError


def expected_key(plan, part_id):
    material = f"{plan.project_id}\0{plan.digest}\0{part_id}".encode("utf-8")
    return "fanout-" + hashlib.sha256(material).hexdigest()


class NativePlanKeyWorkTests(unittest.TestCase):
    def test_complete_native_key_passes_have_linear_part_read_work(self):
        for count in (39, 151):
            with self.subTest(parts=count):
                ids = [f"part{i}" for i in range(count)]
                plan = Plan("native-work", tuple(Part(name, "Keep.") for name in ids))
                expected = [expected_key(plan, name) for name in ids] * 3
                reads = 0
                original_getattribute = Part.__getattribute__

                def observe(part, name):
                    nonlocal reads
                    if name == "id":
                        reads += 1
                    return original_getattribute(part, name)

                # Keep exact native Part and str values. A string subclass
                # would deliberately take the uncached compatibility route.
                # The observer returns each original attribute unchanged.
                with patch.object(Part, "__getattribute__", observe):
                    actual = [plan.idempotency_key(name) for _ in range(3) for name in ids]
                    with self.assertRaisesRegex(PlanError, "^unknown part identifier$"):
                        plan.idempotency_key("missing")
                self.assertEqual(actual, expected)
                # Allow several complete linear passes, but not one full scan
                # per lookup. No elapsed-time or private-cache assertion.
                self.assertLessEqual(reads, count * 4)

    def test_native_and_mutable_parts_keep_live_mixed_membership(self):
        class MutablePart:
            id = "old"
            instruction = "Keep historical admission behavior."
            depends_on = ()
            tags = ()

            def to_dict(self):
                return {"id": self.id, "instruction": self.instruction,
                        "depends_on": [], "tags": []}

        for mutable_first in (False, True):
            with self.subTest(mutable_first=mutable_first):
                mutable = MutablePart()
                native = Part("fixed", "Keep native identity.")
                parts = (mutable, native) if mutable_first else (native, mutable)
                plan = Plan("mixed-membership", parts)
                fixed_key = plan.idempotency_key("fixed")
                self.assertEqual(plan.idempotency_key("old"), expected_key(plan, "old"))
                mutable.id = "new"
                with self.assertRaisesRegex(PlanError, "^unknown part identifier$"):
                    plan.idempotency_key("old")
                self.assertEqual(plan.idempotency_key("new"), expected_key(plan, "new"))
                self.assertEqual(plan.idempotency_key("fixed"), fixed_key)
                self.assertIs(plan.parts[0 if mutable_first else 1], mutable)
                self.assertIs(plan.parts[1 if mutable_first else 0], native)


if __name__ == "__main__":
    unittest.main()
