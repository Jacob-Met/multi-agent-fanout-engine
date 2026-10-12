"""Keep preview payloads and identities bound to one validated plan."""
import copy
import hashlib
import unittest
from unittest.mock import patch

from fanout_engine import EffortRouter, Part, Plan, Route, canonical_json
from fanout_engine.preview import PreviewError, preview_plan


class MutablePart:
    """The native Plan also accepts this historically supported shape."""

    def __init__(self, part_id, instruction, depends_on=(), tags=()):
        self.id = part_id
        self.instruction = instruction
        self.depends_on = list(depends_on)
        self.tags = list(tags)

    def to_dict(self):
        return {
            "id": self.id,
            "instruction": self.instruction,
            "depends_on": list(self.depends_on),
            "tags": list(self.tags),
        }


class PreviewPlanSnapshotTests(unittest.TestCase):
    def plan_and_router(self):
        part = MutablePart("draft", "Write the 日本語 draft.", ("research",),
                           ("z-tag", "a-tag", "z-tag"))
        plan = Plan("preview-snapshot", (part, Part("research", "Read sources.")))
        router = EffortRouter({"model-a": ("low", "high")},
                              pool=(Route("model-a", "low"),))
        return plan, part, router

    def assert_identity_matches_payload(self, report):
        digest = hashlib.sha256(canonical_json(report["plan"]).encode("utf-8")).hexdigest()
        self.assertEqual(report["plan_digest"], digest)
        for row in report["routes"]:
            material = (report["plan"]["project"] + "\0" + digest + "\0" + row["part_id"])
            key = "fanout-" + hashlib.sha256(material.encode("utf-8")).hexdigest()
            self.assertEqual(row["idempotency_key"], key)

    def test_changed_plan_is_refused_before_route_selection(self):
        changes = {
            "instruction": lambda part: setattr(part, "instruction", "Changed instruction."),
            "identifier": lambda part: setattr(part, "id", "revised"),
            "dependencies": lambda part: part.depends_on.clear(),
            "tags": lambda part: part.tags.append("added-tag"),
        }
        for label, change in changes.items():
            with self.subTest(field=label):
                plan, part, router = self.plan_and_router()
                change(part)
                edited = copy.deepcopy(plan.to_dict())
                with patch.object(router, "route_for", wraps=router.route_for) as route_for:
                    with self.assertRaisesRegex(PreviewError, "changed since validation"):
                        preview_plan(plan, router)
                    route_for.assert_not_called()
                self.assertEqual(plan.to_dict(), edited)

    def test_unchanged_part_like_plan_retains_exact_native_identity(self):
        plan, part, router = self.plan_and_router()
        original = copy.deepcopy(plan.to_dict())
        report = preview_plan(plan, router, explicit_routes={"draft": Route("model-a", "high")})
        self.assertEqual(report["plan"], original)
        self.assertEqual(report["plan_digest"], plan.digest)
        self.assertEqual(report["plan"]["parts"][0]["tags"], ["z-tag", "a-tag", "z-tag"])
        self.assertEqual(report["dependency_ready_without_completions"], ["research"])
        self.assertEqual([row["part_id"] for row in report["routes"]], ["draft", "research"])
        self.assertEqual(report["routes"][0]["route_source"], "explicit")
        self.assertEqual(report["routes"][0]["route"], {"model": "model-a", "effort": "high"})
        self.assert_identity_matches_payload(report)
        report["plan"]["parts"][0]["tags"].clear()
        self.assertEqual(plan.to_dict(), original)
        self.assertEqual(part.tags, ["z-tag", "a-tag", "z-tag"])

    def test_routing_callback_cannot_rewrite_the_captured_plan(self):
        plan, part, router = self.plan_and_router()
        expected = preview_plan(plan, router)
        original_route_for = router.route_for

        def change_source(part_id, explicit=None):
            part.instruction = "Changed while routes were being selected."
            part.depends_on.clear()
            part.tags.append("later-tag")
            return original_route_for(part_id, explicit)

        with patch.object(router, "route_for", side_effect=change_source):
            report = preview_plan(plan, router)
        self.assertNotEqual(plan.to_dict(), expected["plan"])
        self.assertEqual(report, expected)
        self.assert_identity_matches_payload(report)
        with self.assertRaisesRegex(PreviewError, "changed since validation"):
            preview_plan(plan, router)

    def test_plan_subclass_keeps_its_existing_readiness_behavior(self):
        class RestrictedPlan(Plan):
            def ready_parts(self, completed=()):
                return ()

        plan = RestrictedPlan("custom-readiness", (Part("one", "Custom plan."),))
        router = EffortRouter({"model-a": ("low",)}, pool=(Route("model-a", "low"),))
        report = preview_plan(plan, router)
        self.assertEqual(report["dependency_ready_without_completions"], [])
        self.assertEqual(report["plan"], plan.to_dict())
        self.assertEqual(report["plan_digest"], plan.digest)
        self.assertEqual(report["routes"][0]["idempotency_key"], plan.idempotency_key("one"))


if __name__ == "__main__":
    unittest.main()
