"""Dispatch the payload whose native identity is recorded in the ledger."""
import copy
import unittest
from unittest.mock import patch

from fanout_engine import (
    EffortRouter, Ledger, LedgerError, Part, Plan, Route, dispatch_ready,
    inspect_project,
)


class MutablePart:
    def __init__(self, part_id, instruction, depends_on=(), tags=()):
        self.id = part_id
        self.instruction = instruction
        self.depends_on = list(depends_on)
        self.tags = list(tags)

    def to_dict(self):
        return {"id": self.id, "instruction": self.instruction,
                "depends_on": list(self.depends_on), "tags": list(self.tags)}


class RecordingHub:
    def __init__(self, on_submit=None, ambiguous=()):
        self.calls = []
        self.parts = []
        self.on_submit = on_submit
        self.ambiguous = set(ambiguous)

    def submit(self, part, *, route, worker_id, idempotency_key):
        self.parts.append(part)
        self.calls.append({"part": part.to_dict(), "route": route,
                           "worker_id": worker_id, "idempotency_key": idempotency_key})
        if self.on_submit is not None:
            self.on_submit(part)
        if part.id in self.ambiguous:
            raise TimeoutError("local receipt unavailable")
        return {"task_id": "local-" + part.id}


class DispatchPlanSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.router = EffortRouter({"model-a": ("low", "high")},
                                  pool=(Route("model-a", "low"),))

    def plan_and_parts(self):
        alpha = MutablePart("alpha", "Prepare the 日本語 source.", tags=("z", "a", "z"))
        beta = MutablePart("beta", "Read the other source.")
        dependent = Part("verify", "Verify the first source.", ("alpha",))
        return Plan("dispatch-snapshot", (alpha, beta, dependent)), alpha, beta

    def dispatch(self, plan, ledger, hub, worker_for=lambda part: "local-worker"):
        return dispatch_ready(plan, ledger, hub, self.router, worker_for=worker_for)

    def test_stale_plan_refuses_before_ledger_or_callbacks_change(self):
        changes = {
            "instruction": lambda part: setattr(part, "instruction", "Edited instruction."),
            "identifier": lambda part: setattr(part, "id", "renamed"),
            "dependencies": lambda part: part.depends_on.append("alpha"),
            "tags": lambda part: part.tags.append("changed"),
        }
        for label, change in changes.items():
            with self.subTest(field=label), Ledger() as ledger:
                plan, _, beta = self.plan_and_parts()
                change(beta)
                original_edited = copy.deepcopy(plan.to_dict())
                workers = []
                hub = RecordingHub()
                with patch.object(self.router, "route_for", wraps=self.router.route_for) as route:
                    with self.assertRaisesRegex(LedgerError, "changed since validation"):
                        self.dispatch(plan, ledger, hub,
                                      lambda part: workers.append(part.id) or "local-worker")
                    route.assert_not_called()
                self.assertIsNone(ledger.project_snapshot(plan.project_id))
                self.assertEqual(ledger.events(plan.project_id), [])
                self.assertEqual(workers, [])
                self.assertEqual(hub.calls, [])
                self.assertEqual(plan.to_dict(), original_edited)

    def test_worker_selection_cannot_rewrite_the_submitted_payload(self):
        plan, alpha, beta = self.plan_and_parts()
        expected = copy.deepcopy(plan.to_dict())
        workers = []

        def choose_worker(part):
            workers.append(part.to_dict())
            alpha.instruction = "Changed inside worker selection."
            beta.tags.append("late-tag")
            beta.depends_on.append("alpha")
            return "local-worker"

        with Ledger() as ledger:
            hub = RecordingHub()
            result = self.dispatch(plan, ledger, hub, choose_worker)
            self.assertEqual(result.started, ("alpha", "beta"))
            self.assertEqual(result.not_ready, ("verify",))
            self.assertEqual(workers, expected["parts"][:2])
            self.assertEqual([call["part"] for call in hub.calls], expected["parts"][:2])
            for call in hub.calls:
                row = ledger.part(plan.project_id, call["part"]["id"])
                self.assertEqual(row["payload"], call["part"])
                self.assertEqual(row["idempotency_key"], call["idempotency_key"])
            self.assertEqual(inspect_project(ledger, plan.project_id)["plan_digest"], plan.digest)

    def test_hub_mutation_keeps_later_payload_and_unknown_no_replay(self):
        plan, _, beta = self.plan_and_parts()
        original = copy.deepcopy(plan.to_dict())

        def change_later_source(part):
            if part.id == "alpha":
                beta.instruction = "Changed by the first local adapter call."

        with Ledger() as ledger:
            hub = RecordingHub(change_later_source, ambiguous=("alpha",))
            result = self.dispatch(plan, ledger, hub)
            self.assertEqual(result.started, ("beta",))
            self.assertEqual(result.outcome_unknown, ("alpha",))
            self.assertEqual(result.not_ready, ("verify",))
            self.assertEqual([call["part"] for call in hub.calls], original["parts"][:2])
            before = copy.deepcopy(ledger.project_snapshot(plan.project_id))
            events = ledger.events(plan.project_id)
            with self.assertRaisesRegex(LedgerError, "changed since validation"):
                self.dispatch(plan, ledger, hub)
            self.assertEqual(ledger.project_snapshot(plan.project_id), before)
            self.assertEqual(ledger.events(plan.project_id), events)
            self.assertEqual(len(hub.calls), 2)
            # Preserve repeated tags while recreating the original native values.
            unchanged = Plan(plan.project_id, tuple(Part(
                row["id"], row["instruction"], row["depends_on"], row["tags"]
            ) for row in original["parts"]))
            replay = self.dispatch(unchanged, ledger, hub)
            self.assertEqual(replay.started, ())
            self.assertEqual(replay.outcome_unknown, ())
            self.assertEqual(replay.not_ready, ("verify",))
            self.assertEqual(len(hub.calls), 2)
            inspect_project(ledger, plan.project_id)

    def test_native_parts_retain_callback_identity_order_and_duplicate_tags(self):
        alpha = Part("alpha", "First.", tags=("z", "a", "z"))
        beta = Part("beta", "Second.")
        plan = Plan("native-identity", (beta, alpha))
        workers = []
        hub = RecordingHub()
        with Ledger() as ledger:
            report = self.dispatch(plan, ledger, hub,
                                   lambda part: workers.append(part) or "local-worker")
            self.assertEqual(report.started, ("beta", "alpha"))
            self.assertIs(workers[0], beta)
            self.assertIs(workers[1], alpha)
            self.assertIs(hub.parts[0], beta)
            self.assertIs(hub.parts[1], alpha)
            self.assertEqual(hub.calls[1]["part"]["tags"], ["z", "a", "z"])
            self.assertEqual(ledger.part(plan.project_id, "alpha")["payload"]["tags"],
                             ["z", "a", "z"])
            inspect_project(ledger, plan.project_id)

    def test_plan_subclass_keeps_custom_readiness_without_extra_submissions(self):
        class RestrictedPlan(Plan):
            def ready_parts(self, completed=()):
                return ()

        plan = RestrictedPlan("custom-readiness", (Part("one", "Custom plan."),))
        workers = []
        hub = RecordingHub()
        with Ledger() as ledger:
            result = self.dispatch(plan, ledger, hub,
                                   lambda part: workers.append(part) or "local-worker")
            self.assertEqual(result.started, ())
            self.assertEqual(result.not_ready, ("one",))
            self.assertEqual(ledger.part_state(plan.project_id, "one"), "queued")
            self.assertEqual(workers, [])
            self.assertEqual(hub.calls, [])


if __name__ == "__main__":
    unittest.main()
