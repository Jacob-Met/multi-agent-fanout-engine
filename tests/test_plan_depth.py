"""Dependency depth must not depend on Python's call-stack limit."""
import sys
import unittest

from fanout_engine import Ledger, Plan, PlanError, inspect_project


def dependency_chain(count, *, cyclic=False):
    parts = [
        {"id": f"part-{index}", "instruction": f"Complete part {index}.",
         "depends_on": [f"part-{index + 1}"] if index + 1 < count else []}
        for index in range(count)
    ]
    if cyclic:
        parts[-1]["depends_on"] = [parts[0]["id"]]
    return {"project": "deep-project", "parts": parts}


class PlanDepthTests(unittest.TestCase):
    def test_deep_valid_plan_retains_declared_order_and_readiness(self):
        document = dependency_chain(2500)
        recursion_limit = sys.getrecursionlimit()
        plan = Plan.from_dict(document)

        self.assertEqual([part.id for part in plan.parts],
                         [part["id"] for part in document["parts"]])
        self.assertEqual([list(part.depends_on) for part in plan.parts],
                         [part["depends_on"] for part in document["parts"]])
        self.assertEqual([part.id for part in plan.ready_parts()], ["part-2499"])
        self.assertEqual([part.id for part in plan.ready_parts({"part-2499"})],
                         ["part-2498", "part-2499"])
        self.assertEqual(sys.getrecursionlimit(), recursion_limit)

    def test_deep_cycle_has_the_native_validation_error(self):
        with self.assertRaisesRegex(PlanError, "dependency graph contains a cycle"):
            Plan.from_dict(dependency_chain(2500, cyclic=True))

    def test_cycle_in_a_later_component_is_not_missed(self):
        document = dependency_chain(1500)
        document["parts"].extend([
            {"id": "cycle-a", "instruction": "a", "depends_on": ["cycle-b"]},
            {"id": "cycle-b", "instruction": "b", "depends_on": ["cycle-a"]},
        ])
        with self.assertRaisesRegex(PlanError, "dependency graph contains a cycle"):
            Plan.from_dict(document)

    def test_deep_stored_plan_remains_inspectable(self):
        plan = Plan.from_dict(dependency_chain(1500))
        with Ledger() as ledger:
            ledger.record_plan(plan)
            report = inspect_project(ledger, plan.project_id)

        self.assertEqual(report["queued_ready_ids"], ["part-1499"])
        self.assertEqual(len(report["blocked_queued_ids"]), 1499)
        self.assertEqual([part["id"] for part in report["parts"]],
                         [part.id for part in plan.parts])

    def test_shared_prerequisites_are_not_cycles(self):
        plan = Plan.from_dict({"project": "shared-project", "parts": [
            {"id": "finish", "instruction": "finish", "depends_on": ["left", "right"]},
            {"id": "left", "instruction": "left", "depends_on": ["start"]},
            {"id": "right", "instruction": "right", "depends_on": ["start", "left"]},
            {"id": "start", "instruction": "start"},
            {"id": "separate", "instruction": "separate"},
        ]})

        self.assertEqual([part.id for part in plan.ready_parts()], ["start", "separate"])
        self.assertEqual([part.id for part in plan.ready_parts({"start", "left"})],
                         ["left", "right", "start", "separate"])


if __name__ == "__main__":
    unittest.main()
