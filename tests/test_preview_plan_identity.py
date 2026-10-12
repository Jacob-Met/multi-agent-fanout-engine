"""Keep preview text, readiness and native identity in one captured plan."""
import copy
import hashlib
import json
import unittest

from fanout_engine import EffortRouter, Part, Plan, Route
from fanout_engine.preview import PreviewError, preview_plan


class MutablePart:
    def __init__(self):
        self.id = "last"
        self.instruction = "Read both sources."
        self.depends_on = ["right", "left"]
        self.tags = ["zeta", "alpha", "zeta"]

    def to_dict(self):
        return {"id": self.id, "instruction": self.instruction,
                "depends_on": list(self.depends_on), "tags": list(self.tags)}


class ObservingRouter(EffortRouter):
    def __init__(self, on_route=None):
        super().__init__(
            {"model-a": ("low", "high")}, pool=(Route("model-a", "low"),),
        )
        self.calls = []
        self.on_route = on_route

    def route_for(self, part_id, explicit=None):
        self.calls.append(part_id)
        if self.on_route is not None:
            self.on_route()
        return super().route_for(part_id, explicit)


def authored_plan():
    source = MutablePart()
    plan = Plan("preview-capture", (
        source, Part("left", "Read the left source."),
        Part("right", "Read the right source."),
    ))
    return source, plan


class PreviewPlanIdentityTests(unittest.TestCase):
    def assert_consistent_identity(self, report):
        document = json.dumps(
            report["plan"], sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
        digest = hashlib.sha256(document).hexdigest()
        self.assertEqual(report["plan_digest"], digest)
        project = report["plan"]["project"]
        for row in report["routes"]:
            material = f"{project}\0{digest}\0{row['part_id']}".encode("utf-8")
            self.assertEqual(
                row["idempotency_key"], "fanout-" + hashlib.sha256(material).hexdigest(),
            )

    def test_stable_mixed_plan_preserves_exact_identity_and_is_detached(self):
        source, plan = authored_plan()
        before = copy.deepcopy(plan.to_dict())
        router = ObservingRouter()
        report = preview_plan(
            plan, router, explicit_routes={"last": Route("model-a", "high")},
        )
        self.assertEqual(report["plan"], before)
        self.assertEqual(report["plan_digest"], plan.digest)
        self.assertEqual(report["dependency_ready_without_completions"], ["left", "right"])
        self.assertEqual(router.calls, ["last", "left", "right"])
        self.assertEqual(report["routes"][0]["route_source"], "explicit")
        self.assertEqual(report["routes"][0]["route"]["effort"], "high")
        self.assert_consistent_identity(report)
        report["plan"]["parts"][0]["tags"].clear()
        report["plan"]["parts"][0]["depends_on"].reverse()
        self.assertEqual(plan.to_dict(), before)
        self.assertIs(plan.parts[0], source)

    def test_changed_valid_source_is_refused_before_route_selection(self):
        edits = {
            "identifier": lambda part: setattr(part, "id", "renamed"),
            "instruction": lambda part: setattr(part, "instruction", "Use other sources."),
            "dependency order": lambda part: part.depends_on.reverse(),
            "readiness": lambda part: part.depends_on.clear(),
            "tag order": lambda part: part.tags.sort(),
            "repeated tags": lambda part: part.tags.pop(),
        }
        for label, edit in edits.items():
            with self.subTest(edit=label):
                source, plan = authored_plan()
                edit(source)
                router = ObservingRouter()
                with self.assertRaisesRegex(PreviewError, "changed since validation"):
                    preview_plan(plan, router)
                self.assertEqual(router.calls, [])

    def test_invalid_changed_source_is_refused_before_route_selection(self):
        for attribute, value in (
            ("instruction", " "), ("depends_on", ["absent"]), ("tags", ["not a tag"]),
        ):
            with self.subTest(attribute=attribute):
                source, plan = authored_plan()
                setattr(source, attribute, value)
                router = ObservingRouter()
                with self.assertRaises(ValueError):
                    preview_plan(plan, router)
                self.assertEqual(router.calls, [])

    def test_route_callback_cannot_mix_new_text_with_captured_identity(self):
        source, plan = authored_plan()
        before = copy.deepcopy(plan.to_dict())

        def change_source():
            source.instruction = "Changed after preview capture."
            source.depends_on.clear()
            source.tags[:] = ["replacement"]

        router = ObservingRouter(change_source)
        report = preview_plan(plan, router)
        self.assertNotEqual(plan.to_dict(), before)
        self.assertEqual(report["plan"], before)
        self.assertEqual(report["dependency_ready_without_completions"], ["left", "right"])
        self.assert_consistent_identity(report)
        self.assertEqual(router.calls, ["last", "left", "right"])
        with self.assertRaisesRegex(PreviewError, "changed since validation"):
            preview_plan(plan, ObservingRouter())


if __name__ == "__main__":
    unittest.main()
