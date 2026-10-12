"""Snapshots keep admitted constructor lists from changing plan identity."""
import unittest

from fanout_engine import (
    EffortRouter, Ledger, Part, Plan, PlanError, Route, dispatch_ready,
    inspect_project,
)


class LocalHub:
    def __init__(self):
        self.calls = []

    def submit(self, part, *, route, worker_id, idempotency_key):
        self.calls.append((part.to_dict(), idempotency_key))
        return {"task_id": "local-" + part.id}


class ConstructorSnapshotTests(unittest.TestCase):
    def dispatch(self, plan, ledger, hub):
        return dispatch_ready(
            plan, ledger, hub,
            EffortRouter({"fixture": ("low",)}, pool=(Route("fixture", "low"),)),
            worker_for=lambda part: "fixture-worker",
        )

    def test_parts_list_detaches_without_copying_parts(self):
        first = Part("first", "Keep.")
        last = Part("last", "Wait.", depends_on=("first",))
        parts = [first, last]
        plan = Plan("parts", parts)
        expected, digest = plan.to_dict(), plan.digest
        keys = [plan.idempotency_key(p.id) for p in plan.parts]
        parts[:] = [Part("first", "Replace."), Part("new", "Unexpected.")]
        self.assertIsInstance(plan.parts, tuple)
        self.assertEqual(plan.to_dict(), expected)
        self.assertEqual(plan.digest, digest)
        self.assertEqual([plan.idempotency_key(p.id) for p in plan.parts], keys)
        self.assertIs(plan.parts[0], first)
        self.assertIs(plan.parts[1], last)
        self.assertEqual([p.id for p in plan.ready_parts()], ["first"])

    def test_dependencies_detach_at_part_construction(self):
        dependencies = ["right", "left"]
        last = Part("last", "Wait.", depends_on=dependencies)
        dependencies.clear()
        plan = Plan("dependencies", (
            Part("left", "Left."), Part("right", "Right."), last,
        ))
        self.assertIsInstance(last.depends_on, tuple)
        self.assertEqual(last.depends_on, ("right", "left"))
        self.assertEqual([p.id for p in plan.ready_parts()], ["left", "right"])
        self.assertEqual([p.id for p in plan.ready_parts({"right"})], ["left", "right"])
        self.assertEqual([p.id for p in plan.ready_parts({"left", "right"})],
                         ["left", "right", "last"])

    def test_tags_detach_without_sorting_or_deduplicating(self):
        tags = ["zeta", "alpha", "zeta"]
        part = Part("one", "Keep tags.", tags=tags)
        tags[:] = ["replacement"]
        plan = Plan("tags", (part,))
        expected = Plan("tags", (
            Part("one", "Keep tags.", tags=("zeta", "alpha", "zeta")),
        ))
        self.assertIsInstance(part.tags, tuple)
        self.assertEqual(part.tags, ("zeta", "alpha", "zeta"))
        self.assertEqual(plan.to_dict(), expected.to_dict())
        self.assertEqual(plan.digest, expected.digest)
        self.assertEqual(plan.idempotency_key("one"), expected.idempotency_key("one"))

    def test_recorded_instruction_matches_local_dispatch(self):
        parts = [Part("one", "Original instruction.")]
        plan = Plan("dispatch", parts)
        with Ledger(":memory:") as ledger:
            ledger.record_plan(plan)
            before = ledger.part(plan.project_id, "one")
            parts[0] = Part("one", "Replacement instruction.")
            hub = LocalHub()
            report = self.dispatch(plan, ledger, hub)
            self.assertEqual(report.started, ("one",))
            self.assertEqual(hub.calls, [(before["payload"], before["idempotency_key"])])
            retained = inspect_project(ledger, plan.project_id)
            self.assertEqual(retained["parts"][0]["instruction"], hub.calls[0][0]["instruction"])
            self.assertEqual(retained["plan_digest"], plan.digest)

    def test_caller_mutation_cannot_unlock_recorded_dependency(self):
        dependencies, tags = ["first"], ["original", "original"]
        last = Part("last", "Wait.", depends_on=dependencies, tags=tags)
        plan = Plan("readiness", (Part("first", "First."), last))
        with Ledger(":memory:") as ledger:
            ledger.record_plan(plan)
            expected = plan.to_dict()
            dependencies.clear()
            tags[:] = ["changed"]
            hub = LocalHub()
            report = self.dispatch(plan, ledger, hub)
            self.assertEqual(plan.to_dict(), expected)
            self.assertEqual(report.started, ("first",))
            self.assertEqual(report.not_ready, ("last",))
            self.assertEqual([p["id"] for p, key in hub.calls], ["first"])
            self.assertEqual(ledger.part_state(plan.project_id, "last"), "queued")
            retained = inspect_project(ledger, plan.project_id)
            self.assertEqual(retained["blocked_queued_ids"], ["last"])
            self.assertEqual(retained["parts"][1]["tags"], ["original", "original"])

    def test_tuple_control_preserves_order_duplicates_and_part_objects(self):
        last = Part("last", "Last.", depends_on=("right", "left"),
                    tags=("zeta", "alpha", "zeta"))
        parts = (Part("left", "Left."), Part("right", "Right."), last)
        plan = Plan("tuple-control", parts)
        self.assertEqual(plan.parts, parts)
        self.assertTrue(all(a is b for a, b in zip(plan.parts, parts)))
        self.assertEqual(last.to_dict(), {
            "id": "last", "instruction": "Last.", "depends_on": ["right", "left"],
            "tags": ["zeta", "alpha", "zeta"],
        })
        with Ledger(":memory:") as ledger:
            ledger.record_plan(plan)
            retained = inspect_project(ledger, plan.project_id)
            self.assertEqual(retained["plan_digest"], plan.digest)
            self.assertEqual(retained["parts"][2]["tags"], ["zeta", "alpha", "zeta"])

    def test_from_dict_control_preserves_normalization_and_detachment(self):
        raw = {"project": "from-dict", "parts": [
            {"id": "left", "instruction": "Left."},
            {"id": "right", "instruction": "Right."},
            {"id": "last", "instruction": "Last.", "depends_on": ["right", "left"],
             "tags": ["zeta", "alpha", "zeta"]},
        ]}
        plan = Plan.from_dict(raw)
        expected = Plan("from-dict", (
            Part("left", "Left."), Part("right", "Right."),
            Part("last", "Last.", depends_on=("right", "left"), tags=("alpha", "zeta")),
        ))
        raw["parts"][2]["depends_on"].clear()
        raw["parts"][2]["tags"].append("changed")
        raw["parts"].clear()
        self.assertEqual(plan.to_dict(), expected.to_dict())
        self.assertEqual(plan.digest, expected.digest)
        self.assertEqual(plan.idempotency_key("last"), expected.idempotency_key("last"))
        self.assertEqual(plan.parts[2].depends_on, ("right", "left"))
        self.assertEqual(plan.parts[2].tags, ("alpha", "zeta"))

    def test_existing_invalid_graph_validation_is_preserved(self):
        cases = {
            "empty": [],
            "duplicate-id": [Part("same", "A."), Part("same", "B.")],
            "empty-instruction": [Part("one", " ")],
            "unknown-dependency": [Part("one", "A.", depends_on=["missing"])],
            "duplicate-dependency": [
                Part("first", "A."), Part("last", "B.", depends_on=["first", "first"]),
            ],
            "self-dependency": [Part("one", "A.", depends_on=["one"])],
            "cycle": [
                Part("one", "A.", depends_on=["two"]),
                Part("two", "B.", depends_on=["one"]),
            ],
            "invalid-tag": [Part("one", "A.", tags=["not a tag"])],
        }
        for label, parts in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(PlanError):
                    Plan("invalid-control", parts)


if __name__ == "__main__":
    unittest.main()
