"""Public identity and copy compatibility for repeated plan-key lookups."""
from __future__ import annotations

import copy
from dataclasses import asdict, replace
import hashlib
import pickle
import unittest

from fanout_engine.plan import Part, Plan, PlanError


def expected_key(plan, part_id):
    material = f"{plan.project_id}\0{plan.digest}\0{part_id}".encode("utf-8")
    return "fanout-" + hashlib.sha256(material).hexdigest()


class PlanKeyIdentityTests(unittest.TestCase):
    def test_repeated_keys_match_exact_public_identity(self):
        plan = Plan.from_dict({"project": "repeated-keys", "parts": [
            {"id": f"p{i}", "instruction": f"Unicode fixture π {i}",
             "depends_on": [f"p{i-1}"] if i else [], "tags": ["sample", "sample"]}
            for i in range(1200)
        ]})
        before = (plan.to_dict(), plan.digest, asdict(plan), repr(plan), hash(plan))
        keys = {part.id: expected_key(plan, part.id) for part in plan.parts}
        for parts in (plan.parts, tuple(reversed(plan.parts))):
            for part in parts:
                self.assertEqual(plan.idempotency_key(part.id), keys[part.id])
        self.assertEqual((plan.to_dict(), plan.digest, asdict(plan), repr(plan), hash(plan)), before)

    def test_refusals_unchanged_before_and_after_known_key(self):
        plan = Plan("identity", (Part("one", "First"),))
        for populated in (False, True):
            if populated:
                plan.idempotency_key("one")
            for value in ("", "space id", "1invalid", "x" * 65, None, 7, []):
                with self.subTest(populated=populated, value=repr(value)):
                    with self.assertRaisesRegex(PlanError, "^invalid part identifier$"):
                        plan.idempotency_key(value)
            with self.assertRaisesRegex(PlanError, "^unknown part identifier$"):
                plan.idempotency_key("missing")

    def test_copy_pickle_and_replacement_keep_their_own_membership(self):
        plan = Plan("copies", (Part("one", "First"), Part("two", "Second", ("one",))))
        plan.idempotency_key("one")
        for restored in (copy.copy(plan), copy.deepcopy(plan), pickle.loads(pickle.dumps(plan))):
            self.assertEqual(restored, plan)
            self.assertEqual(asdict(restored), asdict(plan))
            for part in plan.parts:
                self.assertEqual(restored.idempotency_key(part.id), expected_key(plan, part.id))
        replaced = replace(plan, parts=(Part("three", "Replacement"),))
        self.assertEqual(replaced.idempotency_key("three"), expected_key(replaced, "three"))
        with self.assertRaisesRegex(PlanError, "^unknown part identifier$"):
            replaced.idempotency_key("one")
        self.assertEqual(plan.idempotency_key("one"), expected_key(plan, "one"))

    def test_direct_list_snapshot_keeps_accepted_membership(self):
        # The accepted constructor snapshots its caller's list. Repeated key
        # lookup must retain that snapshot before and after external mutation.
        parts = [Part("one", "First")]
        plan = Plan("mutable-compatibility", parts)
        self.assertEqual(plan.idempotency_key("one"), expected_key(plan, "one"))
        parts.append(Part("two", "Second"))
        with self.assertRaisesRegex(PlanError, "^unknown part identifier$"):
            plan.idempotency_key("two")
        parts.pop(0)
        self.assertEqual(plan.idempotency_key("one"), expected_key(plan, "one"))

    def test_tuple_of_mutable_part_objects_keeps_legacy_membership(self):
        class MutablePart:
            id = "one"
            instruction = "First"
            depends_on = ()
            tags = ()

            def to_dict(self):
                return {"id": self.id, "instruction": self.instruction,
                        "depends_on": [], "tags": []}

        part = MutablePart()
        plan = Plan("duck-compatibility", (part,))
        self.assertEqual(plan.idempotency_key("one"), expected_key(plan, "one"))
        part.id = "two"
        self.assertEqual(plan.idempotency_key("two"), expected_key(plan, "two"))
        with self.assertRaisesRegex(PlanError, "^unknown part identifier$"):
            plan.idempotency_key("one")

    def test_tuple_subclass_snapshot_keeps_accepted_membership(self):
        class MutableTuple(tuple):
            def __new__(cls, values):
                value = super().__new__(cls, values)
                value.rows = list(values)
                return value

            def __iter__(self):
                return iter(self.rows)

        parts = MutableTuple([Part("one", "First")])
        plan = Plan("tuple-compatibility", parts)
        self.assertEqual(plan.idempotency_key("one"), expected_key(plan, "one"))
        parts.rows[:] = [Part("two", "Second")]
        with self.assertRaisesRegex(PlanError, "^unknown part identifier$"):
            plan.idempotency_key("two")
        self.assertEqual(plan.idempotency_key("one"), expected_key(plan, "one"))


if __name__ == "__main__":
    unittest.main()
