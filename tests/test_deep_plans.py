import itertools
import tempfile
import unittest
from pathlib import Path

from fanout_engine import (
    EffortRouter, Ledger, Plan, PlanError, Route, dispatch_ready, inspect_project,
)


def chain_document(count=1500):
    return {
        "project": "deep-plan",
        "parts": [
            {"id": f"p{i}", "instruction": "Local reference work.",
             "depends_on": [f"p{i + 1}"] if i + 1 < count else []}
            for i in range(count)
        ],
    }


class DeepPlanTests(unittest.TestCase):
    def test_deep_chain_keeps_authored_order_and_readiness(self):
        plan = Plan.from_dict(chain_document())
        self.assertEqual([p.id for p in plan.parts], [f"p{i}" for i in range(1500)])
        self.assertEqual([p.id for p in plan.ready_parts()], ["p1499"])
        self.assertEqual([p.id for p in plan.ready_parts({"p1499"})],
                         ["p1498", "p1499"])
        reloaded = Plan.from_dict(plan.to_dict())
        self.assertEqual(reloaded.digest, plan.digest)
        self.assertEqual(reloaded.idempotency_key("p0"), plan.idempotency_key("p0"))

    def test_deep_cycle_raises_the_existing_plan_error(self):
        document = chain_document()
        document["parts"][-1]["depends_on"] = ["p0"]
        with self.assertRaisesRegex(PlanError, "^dependency graph contains a cycle$"):
            Plan.from_dict(document)

    def test_disconnected_cycle_is_not_hidden_by_completed_walk(self):
        document = chain_document()
        document["parts"].extend([
            {"id": "cycle-a", "instruction": "a", "depends_on": ["cycle-b"]},
            {"id": "cycle-b", "instruction": "b", "depends_on": ["cycle-a"]},
        ])
        with self.assertRaisesRegex(PlanError, "^dependency graph contains a cycle$"):
            Plan.from_dict(document)

    def test_shared_prerequisites_preserve_existing_identity(self):
        # These identities were recorded with the original recursive validator.
        plan = Plan.from_dict({"project": "identity-check", "parts": [
            {"id": "publish", "instruction": "Publish approved result.",
             "depends_on": ["draft", "check"]},
            {"id": "draft", "instruction": "Write summary.",
             "depends_on": ["research"], "tags": ["writing"]},
            {"id": "check", "instruction": "Check results.",
             "depends_on": ["research"]},
            {"id": "research", "instruction": "Read source material."},
            {"id": "independent", "instruction": "Record context."},
        ]})
        self.assertEqual(plan.digest,
                         "57099d33f4af4beece916af43425b46235d8f014fe5c1f627e3101749831ec3e")
        self.assertEqual(plan.idempotency_key("publish"),
                         "fanout-7a02d28b08e5960d5b4d4a9cec641afb7e9ea3ef36f410769d50698c09329034")
        self.assertEqual(plan.parts[0].depends_on, ("draft", "check"))
        self.assertEqual([p.id for p in plan.ready_parts()], ["research", "independent"])
        self.assertEqual([p.id for p in plan.ready_parts({"draft", "check"})],
                         ["publish", "research", "independent"])

    def test_small_graphs_match_independent_ordering_oracle(self):
        ids = ("a", "b", "c")
        edges = tuple((child, parent) for child in ids for parent in ids if child != parent)
        for mask in range(1 << len(edges)):
            selected = tuple(edge for bit, edge in enumerate(edges) if mask & (1 << bit))
            has_valid_order = any(
                all(order.index(parent) < order.index(child) for child, parent in selected)
                for order in itertools.permutations(ids)
            )
            document = {"project": "small-graph", "parts": [
                {"id": child, "instruction": child,
                 "depends_on": [parent for node, parent in selected if node == child]}
                for child in ids
            ]}
            with self.subTest(edges=selected):
                if has_valid_order:
                    self.assertEqual(len(Plan.from_dict(document).parts), 3)
                else:
                    with self.assertRaisesRegex(PlanError, "dependency graph contains a cycle"):
                        Plan.from_dict(document)

    def test_deep_retained_plan_reopens_inspects_and_dispatches_one_ready_part(self):
        plan = Plan.from_dict(chain_document())
        calls = []

        class LocalHub:
            def submit(self, part, *, route, worker_id, idempotency_key):
                calls.append((part.id, idempotency_key))
                return {"task_id": "local-task"}

        router = EffortRouter({"local-model": ["low"]}, pool=[Route("local-model", "low")])
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "ledger.sqlite")
            with Ledger(database) as ledger:
                ledger.record_plan(plan)
            with Ledger(database) as ledger:
                snapshot = inspect_project(ledger, plan.project_id)
                self.assertEqual(snapshot["queued_ready_ids"], ["p1499"])
                self.assertEqual(len(snapshot["blocked_queued_ids"]), 1499)
                report = dispatch_ready(plan, ledger, LocalHub(), router,
                                        worker_for=lambda part: "local-worker")
                self.assertEqual(report.started, ("p1499",))
                self.assertEqual(report.outcome_unknown, ())
                self.assertEqual(calls, [("p1499", plan.idempotency_key("p1499"))])
                self.assertEqual(ledger.part_state(plan.project_id, "p1498"), "queued")
                self.assertEqual(inspect_project(ledger, plan.project_id)["queued_ready_ids"], [])


if __name__ == "__main__":
    unittest.main()
