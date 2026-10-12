"""Graph admission must depend on edges, not interpreter call-stack depth."""
import hashlib
import itertools
import json
import sys
import unittest

from fanout_engine import Plan, PlanError


def chain_document(length, *, reverse=False, cycle=False):
    parts = [
        {"id": f"part{i}", "instruction": "Review synthetic input.",
         "depends_on": [f"part{i - 1}"] if i else [], "tags": []}
        for i in range(length)
    ]
    if cycle:
        parts[0]["depends_on"] = [f"part{length - 1}"]
    if reverse:
        parts.reverse()
    return {"project": "graph-review", "parts": parts}


class PlanGraphTests(unittest.TestCase):
    def test_deep_chain_preserves_authored_document_and_identity(self):
        recursion_limit = sys.getrecursionlimit()
        for reverse in (False, True):
            document = chain_document(1500, reverse=reverse)
            with self.subTest(reverse=reverse):
                plan = Plan.from_dict(document)
                self.assertEqual(plan.to_dict(), document)
                canonical = json.dumps(document, sort_keys=True,
                                       separators=(",", ":"), ensure_ascii=False)
                expected_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                self.assertEqual(plan.digest, expected_digest)
                material = f"graph-review\0{expected_digest}\0part1499".encode("utf-8")
                self.assertEqual(plan.idempotency_key("part1499"),
                                 "fanout-" + hashlib.sha256(material).hexdigest())
                self.assertEqual([part.id for part in plan.ready_parts()], ["part0"])
                expected_ready = ["part1", "part0"] if reverse else ["part0", "part1"]
                self.assertEqual([part.id for part in plan.ready_parts({"part0"})],
                                 expected_ready)
        self.assertEqual(sys.getrecursionlimit(), recursion_limit)

    def test_deep_cycles_raise_the_native_plan_error(self):
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                with self.assertRaisesRegex(PlanError, "^dependency graph contains a cycle$"):
                    Plan.from_dict(chain_document(1500, reverse=reverse, cycle=True))

    def test_shared_prerequisites_and_a_separate_component_are_acyclic(self):
        document = {"project": "shared-prerequisites", "parts": [
            {"id": "publish", "instruction": "Publish.", "depends_on": ["review", "draft"]},
            {"id": "review", "instruction": "Review.", "depends_on": ["draft", "research"]},
            {"id": "draft", "instruction": "Draft.", "depends_on": ["research"]},
            {"id": "research", "instruction": "Research."},
            {"id": "separate", "instruction": "Independent."},
        ]}
        plan = Plan.from_dict(document)
        self.assertEqual([part.id for part in plan.parts],
                         ["publish", "review", "draft", "research", "separate"])
        self.assertEqual([part.id for part in plan.ready_parts()], ["research", "separate"])
        self.assertEqual(plan.parts[0].depends_on, ("review", "draft"))

    def test_a_cycle_in_a_later_component_is_still_rejected(self):
        with self.assertRaisesRegex(PlanError, "^dependency graph contains a cycle$"):
            Plan.from_dict({"project": "mixed-components", "parts": [
                {"id": "independent", "instruction": "Independent."},
                {"id": "first", "instruction": "First.", "depends_on": ["second"]},
                {"id": "second", "instruction": "Second.", "depends_on": ["third"]},
                {"id": "third", "instruction": "Third.", "depends_on": ["first"]},
            ]})

    def test_all_three_node_graphs_match_possible_topological_orders(self):
        # Independent finite oracle: an acyclic graph has at least one ordering
        # in which every prerequisite appears before the part that uses it.
        nodes = ("alpha", "beta", "gamma")
        orders = list(itertools.permutations(nodes))
        possible_edges = [(node, parent) for node in nodes for parent in nodes if node != parent]
        for mask in range(1 << len(possible_edges)):
            edges = [edge for bit, edge in enumerate(possible_edges) if mask & (1 << bit)]
            acyclic = any(all(order.index(parent) < order.index(node) for node, parent in edges)
                          for order in orders)
            for authored_order in orders:
                document = {"project": "finite-graph", "parts": [
                    {"id": node, "instruction": "Check graph.",
                     "depends_on": [parent for child, parent in edges if child == node]}
                    for node in authored_order
                ]}
                with self.subTest(edges=edges, authored_order=authored_order):
                    if acyclic:
                        plan = Plan.from_dict(document)
                        self.assertEqual(tuple(part.id for part in plan.parts), authored_order)
                    else:
                        with self.assertRaisesRegex(PlanError, "^dependency graph contains a cycle$"):
                            Plan.from_dict(document)


if __name__ == "__main__":
    unittest.main()
