"""Regression coverage for dependency depth independent of interpreter recursion."""
import sys
import unittest

from fanout_engine import Part, Plan, PlanError


def chain_parts(count, *, cycle_to=None):
    """Put each dependent before its prerequisite to exercise the whole depth."""
    return [
        {
            "id": f"part{index}",
            "instruction": "Process the input.",
            "depends_on": (
                [f"part{index + 1}"] if index + 1 < count
                else ([f"part{cycle_to}"] if cycle_to is not None else [])
            ),
            "tags": [],
        }
        for index in range(count)
    ]


class PlanDepthTests(unittest.TestCase):
    def setUp(self):
        self.count = max(2500, sys.getrecursionlimit() + 100)

    def test_long_chain_accepts_both_public_construction_paths(self):
        parts = chain_parts(self.count)
        document = {"project": "deep-chain", "parts": parts}
        constructors = (
            lambda: Plan.from_dict(document),
            lambda: Plan("deep-chain", tuple(
                Part(part["id"], part["instruction"], tuple(part["depends_on"]))
                for part in parts
            )),
        )
        for construct in constructors:
            with self.subTest(construct=construct):
                plan = construct()
                self.assertEqual(plan.to_dict(), document)
                self.assertEqual([part.id for part in plan.ready_parts()],
                                 [f"part{self.count - 1}"])
                self.assertEqual(
                    [part.id for part in plan.ready_parts({f"part{self.count - 1}"})],
                    [f"part{self.count - 2}", f"part{self.count - 1}"],
                )

    def test_long_cycle_raises_domain_error(self):
        with self.assertRaisesRegex(PlanError, "dependency graph contains a cycle"):
            Plan.from_dict({"project": "deep-cycle", "parts":
                            chain_parts(self.count, cycle_to=0)})

    def test_cycle_in_later_component_is_not_skipped(self):
        parts = [{"id": "independent", "instruction": "Separate valid work."}]
        parts.extend(chain_parts(self.count, cycle_to=self.count // 2))
        with self.assertRaisesRegex(PlanError, "dependency graph contains a cycle"):
            Plan.from_dict({"project": "later-cycle", "parts": parts})

    def test_deep_shared_dependencies_keep_authored_order(self):
        parts = chain_parts(self.count)
        for index, part in enumerate(parts[:-2]):
            part["depends_on"].append(f"part{index + 2}")
        document = {"project": "deep-shared", "parts": parts}
        plan = Plan.from_dict(document)
        self.assertEqual(plan.to_dict(), document)
        self.assertEqual([part.id for part in plan.ready_parts()],
                         [f"part{self.count - 1}"])

    def test_existing_identity_and_dependency_order_are_unchanged(self):
        document = {
            "project": "identity-control",
            "parts": [
                {"id": "publish", "instruction": "Publish the reviewed result.",
                 "depends_on": ["review", "prepare"], "tags": ["final"]},
                {"id": "review", "instruction": "Review the source.",
                 "depends_on": ["prepare"], "tags": []},
                {"id": "prepare", "instruction": "Prepare the source.",
                 "depends_on": [], "tags": ["source"]},
            ],
        }
        plan = Plan.from_dict(document)
        self.assertEqual(plan.to_dict(), document)
        # Captured from the unchanged upstream implementation before the repair.
        self.assertEqual(plan.digest,
                         "90d8db4ae1d7c3439c9fc34488da66046afee0bbeb6f7d51e7cd898076d3910d")
        self.assertEqual(plan.idempotency_key("publish"),
                         "fanout-e9acc73f352d84a5f026aef93a03e710f47c4a86fe7502028c2fbe798688c71b")
        self.assertEqual(plan.idempotency_key("prepare"),
                         "fanout-e25bf33e910afaf81dc6369b6533c97088abd7c0585bfc95afb67eb1cffd4685")


if __name__ == "__main__":
    unittest.main()
