"""Native dependency depth must not depend on the Python call stack."""
import hashlib
import json
import unittest

from fanout_engine import Plan, PlanError


def chain(size=1500):
    # Reverse dependency order forces traversal through the complete chain.
    return [{"id": f"part{i}", "instruction": "Prepare the next result.",
             "depends_on": [f"part{i + 1}"] if i + 1 < size else []}
            for i in range(size)]


class DeepPlanGraphTests(unittest.TestCase):
    def test_deep_acyclic_chain_keeps_order_identity_and_readiness(self):
        parts = chain()
        plan = Plan.from_dict({"project": "deep-chain", "parts": parts})
        expected = {"project": "deep-chain", "parts": [
            {**part, "tags": []} for part in parts]}
        encoded = json.dumps(expected, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8")
        digest = hashlib.sha256(encoded).hexdigest()
        self.assertEqual(plan.to_dict(), expected)
        self.assertEqual(plan.digest, digest)
        self.assertEqual([part.id for part in plan.ready_parts()], ["part1499"])
        self.assertEqual([part.id for part in plan.ready_parts({"part1499"})],
                         ["part1498", "part1499"])
        expected_key = "fanout-" + hashlib.sha256(
            f"deep-chain\0{digest}\0part0".encode("utf-8")).hexdigest()
        self.assertEqual(plan.idempotency_key("part0"), expected_key)

    def test_deep_cycles_raise_the_domain_error(self):
        for back_edge in ("part0", "part1400"):
            with self.subTest(back_edge=back_edge):
                parts = chain()
                parts[-1]["depends_on"] = [back_edge]
                with self.assertRaisesRegex(PlanError, "dependency graph contains a cycle"):
                    Plan.from_dict({"project": "deep-cycle", "parts": parts})

    def test_shared_prerequisites_are_not_cycles(self):
        parts = [
            {"id": "publish", "instruction": "Publish.", "depends_on": ["review", "build"]},
            {"id": "review", "instruction": "Review.", "depends_on": ["source"]},
            {"id": "source", "instruction": "Prepare source."},
            {"id": "build", "instruction": "Build.", "depends_on": ["source"]},
            {"id": "independent", "instruction": "Work independently."},
        ]
        plan = Plan.from_dict({"project": "shared", "parts": parts})
        self.assertEqual([part.id for part in plan.parts], [part["id"] for part in parts])
        self.assertEqual(plan.parts[0].depends_on, ("review", "build"))
        self.assertEqual([part.id for part in plan.ready_parts()], ["source", "independent"])
        self.assertEqual([part.id for part in plan.ready_parts({"source"})],
                         ["review", "source", "build", "independent"])

    def test_disconnected_cycle_is_checked_after_completed_traversal(self):
        parts = chain()
        parts.extend([
            {"id": "cycleA", "instruction": "A.", "depends_on": ["cycleB"]},
            {"id": "cycleB", "instruction": "B.", "depends_on": ["cycleA"]},
        ])
        with self.assertRaisesRegex(PlanError, "dependency graph contains a cycle"):
            Plan.from_dict({"project": "disconnected", "parts": parts})


if __name__ == "__main__":
    unittest.main()
