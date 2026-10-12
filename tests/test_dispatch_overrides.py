"""Explicit dispatch choices must be admitted before any work starts."""
from collections import UserDict
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fanout_engine import EffortRouter, Ledger, Part, Plan, Route, dispatch_ready


LOW = Route("model-a", "low")
HIGH = Route("model-a", "high")


class RecordingHub:
    def __init__(self, on_submit=None, ambiguous=()):
        self.calls = []
        self.on_submit = on_submit
        self.ambiguous = set(ambiguous)

    def submit(self, part, *, route, worker_id, idempotency_key):
        self.calls.append((part.id, route, worker_id, idempotency_key))
        if self.on_submit is not None:
            self.on_submit(part)
        if part.id in self.ambiguous:
            raise TimeoutError("Local acceptance is unknown.")
        return {"task_id": "local-" + part.id}


class DispatchOverrideTests(unittest.TestCase):
    def setUp(self):
        self.plan = Plan("override-review", (
            Part("alpha", "First local task."),
            Part("beta", "Second local task."),
            Part("after_alpha", "Dependent local task.", depends_on=("alpha",)),
        ))
        self.router = EffortRouter({"model-a": ("low", "high")}, pool=(LOW,))

    def assert_refused_before_effects(self, overrides, message):
        hub, workers = RecordingHub(), []
        with Ledger() as ledger:
            with self.assertRaisesRegex(ValueError, message):
                dispatch_ready(
                    self.plan, ledger, hub, self.router,
                    worker_for=lambda part: workers.append(part.id) or "local-worker",
                    explicit_routes=overrides,
                )
            self.assertIsNone(ledger.project_snapshot(self.plan.project_id))
            self.assertEqual(ledger.events(self.plan.project_id), [])
        self.assertEqual(workers, [])
        self.assertEqual(hub.calls, [])

    def test_unknown_override_keys_refuse_before_plan_or_callbacks(self):
        for key in ("alpah", "ALPHA", "", 1, None):
            with self.subTest(key=key):
                self.assert_refused_before_effects(
                    {"alpha": HIGH, key: LOW}, "unknown part identifier")

    def test_non_route_values_cannot_silently_select_the_pool(self):
        for route in (None, False, "model-a", {"model": "model-a", "effort": "high"}, object()):
            with self.subTest(route=route):
                self.assert_refused_before_effects(
                    {"alpha": HIGH, "beta": route}, "must be a native Route")

    def test_non_mappings_including_empty_values_are_refused(self):
        for overrides in ([], (), "", False, 0, [("alpha", HIGH)]):
            with self.subTest(overrides=overrides):
                self.assert_refused_before_effects(overrides, "must map part identifiers")

    def test_invalid_value_for_known_blocked_part_is_not_ignored(self):
        self.assert_refused_before_effects(
            {"after_alpha": None}, "must be a native Route")

    def test_valid_partial_and_empty_overrides_keep_native_routes_and_order(self):
        for overrides, expected in ((None, [LOW, LOW]), ({}, [LOW, LOW]),
                                    ({"beta": HIGH}, [LOW, HIGH])):
            with self.subTest(overrides=overrides), Ledger() as ledger:
                hub = RecordingHub()
                result = dispatch_ready(
                    self.plan, ledger, hub, self.router, worker_for=lambda _: "local-worker",
                    explicit_routes=overrides,
                )
                self.assertEqual(result.started, ("alpha", "beta"))
                self.assertEqual(result.outcome_unknown, ())
                self.assertEqual(result.not_ready, ("after_alpha",))
                self.assertEqual(hub.calls, [
                    (part_id, route, "local-worker", self.plan.idempotency_key(part_id))
                    for part_id, route in zip(("alpha", "beta"), expected)
                ])
                self.assertEqual([event["event"] for event in ledger.events(self.plan.project_id)],
                                 ["plan_recorded", "dispatch_started", "dispatch_accepted",
                                  "dispatch_started", "dispatch_accepted"])

    def test_native_mapping_and_falsy_mapping_keep_explicit_selection(self):
        class FalsyMapping(UserDict):
            def __bool__(self):
                return False

        for overrides in (UserDict({"alpha": HIGH}), FalsyMapping({"alpha": HIGH})):
            with self.subTest(kind=type(overrides).__name__), Ledger() as ledger:
                hub = RecordingHub()
                dispatch_ready(
                    self.plan, ledger, hub, self.router, worker_for=lambda _: "local-worker",
                    explicit_routes=overrides,
                )
                self.assertEqual([call[1] for call in hub.calls], [HIGH, LOW])
                self.assertEqual(dict(overrides), {"alpha": HIGH})

    def test_worker_and_hub_changes_to_caller_mapping_do_not_retarget_this_call(self):
        overrides = {"alpha": HIGH, "beta": HIGH}
        def worker_for(part):
            overrides.clear()
            return "local-worker"
        def on_submit(part):
            overrides["beta"] = LOW
        hub = RecordingHub(on_submit=on_submit)
        with Ledger() as ledger:
            dispatch_ready(self.plan, ledger, hub, self.router, worker_for=worker_for,
                           explicit_routes=overrides)
            self.assertEqual([call[1] for call in hub.calls], [HIGH, HIGH])
            self.assertEqual(ledger.part(self.plan.project_id, "alpha")["route"],
                             {"model": "model-a", "effort": "high"})
            self.assertEqual(ledger.part(self.plan.project_id, "beta")["route"],
                             {"model": "model-a", "effort": "high"})

    def test_refused_overrides_preserve_reopened_state_and_events(self):
        hub = RecordingHub(ambiguous=("alpha",))
        with TemporaryDirectory() as temporary:
            database = str(Path(temporary) / "ledger.sqlite")
            with Ledger(database) as ledger:
                dispatch_ready(self.plan, ledger, hub, self.router,
                               worker_for=lambda _: "local-worker")
                before = ledger.project_snapshot(self.plan.project_id)
                events = ledger.events(self.plan.project_id)
            with Ledger(database) as ledger:
                workers = []
                with self.assertRaisesRegex(ValueError, "unknown part identifier"):
                    dispatch_ready(
                        self.plan, ledger, hub, self.router,
                        worker_for=lambda part: workers.append(part.id) or "local-worker",
                        explicit_routes={"alpah": HIGH},
                    )
                self.assertEqual(ledger.project_snapshot(self.plan.project_id), before)
                self.assertEqual(ledger.events(self.plan.project_id), events)
                self.assertEqual(workers, [])
                self.assertEqual([call[0] for call in hub.calls], ["alpha", "beta"])
            with Ledger(database) as ledger:
                self.assertEqual(ledger.project_snapshot(self.plan.project_id), before)
                self.assertEqual(ledger.events(self.plan.project_id), events)

    def test_catalog_authority_stays_at_the_existing_eligible_part_boundary(self):
        outside = Route("outside-catalog", "low")
        hub = RecordingHub()
        with Ledger() as ledger:
            with self.assertRaisesRegex(ValueError, "authorized catalog"):
                dispatch_ready(
                    self.plan, ledger, hub, self.router, worker_for=lambda _: "local-worker",
                    explicit_routes={"beta": outside},
                )
            self.assertEqual([call[0] for call in hub.calls], ["alpha"])
            self.assertEqual(ledger.part_state(self.plan.project_id, "alpha"), "running")
            self.assertEqual(ledger.part_state(self.plan.project_id, "beta"), "queued")
            self.assertEqual(ledger.events(self.plan.project_id, "beta"), [])

    def test_known_blocked_and_inflight_overrides_do_not_consult_authority(self):
        outside = Route("outside-catalog", "low")
        hub = RecordingHub()
        with Ledger() as ledger:
            dispatch_ready(self.plan, ledger, hub, self.router,
                           worker_for=lambda _: "local-worker")
            before = ledger.events(self.plan.project_id)
            def unexpected_worker(_):
                raise AssertionError("No eligible queued part should select a worker.")
            result = dispatch_ready(
                self.plan, ledger, hub, self.router, worker_for=unexpected_worker,
                explicit_routes={"alpha": outside, "beta": outside, "after_alpha": outside},
            )
            self.assertEqual(result.started, ())
            self.assertEqual(result.not_ready, ("after_alpha",))
            self.assertEqual(ledger.events(self.plan.project_id), before)
            self.assertEqual([call[0] for call in hub.calls], ["alpha", "beta"])


if __name__ == "__main__":
    unittest.main()
