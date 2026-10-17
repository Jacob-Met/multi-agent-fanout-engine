"""Dispatch callbacks must use the same native identity as persisted work."""
import copy
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from fanout_engine import EffortRouter, Ledger, Part, Plan, Route, dispatch_ready, inspect_project
from fanout_engine.ledger import LedgerError


LOW = Route("local-model", "low")
HIGH = Route("local-model", "high")


class MutablePart:
    def __init__(self, part_id, instruction, depends_on=(), tags=()):
        self.id = part_id
        self.instruction = instruction
        self.depends_on = list(depends_on)
        self.tags = list(tags)

    def to_dict(self):
        return {"id": self.id, "instruction": self.instruction,
                "depends_on": list(self.depends_on), "tags": list(self.tags)}


def authored_plan():
    first = MutablePart("first", "Read the first source.", tags=("zeta", "alpha", "zeta"))
    last = MutablePart("last", "Use the first result.", depends_on=("first",))
    peer = MutablePart("peer", "Read the independent source.")
    return (first, last, peer), Plan("dispatch-capture", (first, last, peer))


def native_plan(document):
    return Plan(document["project"], tuple(
        Part(part["id"], part["instruction"], part["depends_on"], part["tags"])
        for part in document["parts"]
    ))


def expected_key(document, part_id):
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    material = (document["project"] + "\0" + digest + "\0" + part_id).encode("utf-8")
    return "fanout-" + hashlib.sha256(material).hexdigest()


class ObservedRouter(EffortRouter):
    def __init__(self, callback=lambda: None):
        super().__init__({"local-model": ("low", "high")}, pool=(LOW,))
        self.callback = callback
        self.calls = []

    def route_for(self, part_id, explicit=None):
        self.callback()
        self.calls.append((part_id, explicit))
        return super().route_for(part_id, explicit)


class CallbackReceipt(dict):
    def __init__(self, part_id, callback):
        super().__init__(task_id="local-test-only-" + part_id)
        self.callback = callback

    def get(self, key, default=None):
        self.callback()
        return super().get(key, default)


class LocalHub:
    def __init__(self, callback=lambda: None, receipt_callback=lambda: None, timeout=False):
        self.callback = callback
        self.receipt_callback = receipt_callback
        self.timeout = timeout
        self.calls = []

    def submit(self, part, *, route, worker_id, idempotency_key):
        self.callback()
        self.calls.append({"part": part.to_dict(), "route": route, "worker": worker_id,
                           "key": idempotency_key})
        if self.timeout and len(self.calls) == 1:
            raise TimeoutError("test-only acceptance ambiguity")
        return CallbackReceipt(part.id, self.receipt_callback)


class CallbackRoutes(Mapping):
    def __init__(self, callback):
        self.callback = callback

    def __iter__(self):
        self.callback()
        return iter(("peer",))

    def __len__(self):
        return 1

    def __getitem__(self, key):
        if key != "peer":
            raise KeyError(key)
        return HIGH


class DispatchPlanIdentityTests(unittest.TestCase):
    def run_callback_case(self, phase):
        sources, plan = authored_plan()
        document = copy.deepcopy(plan.to_dict())
        pristine = native_plan(document)
        changed = []

        def mutate():
            if changed:
                return
            changed.append(phase)
            for source in sources:
                source.id = "edited-" + source.id
                source.instruction = "Edited inside " + phase + "."
                source.depends_on.clear()
                source.tags[:] = ["replacement"]

        noop = lambda: None
        router = ObservedRouter(mutate if phase == "router" else noop)
        hub = LocalHub(mutate if phase in ("hub", "timeout") else noop,
                       mutate if phase == "receipt" else noop, timeout=phase == "timeout")
        workers = []

        def worker_for(part):
            if phase == "worker":
                mutate()
            workers.append(part.to_dict())
            return "local-worker-" + part.id

        routes = CallbackRoutes(mutate) if phase == "routes" else {"peer": HIGH}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            with Ledger(str(path)) as ledger:
                report = dispatch_ready(plan, ledger, hub, router, worker_for=worker_for,
                                        explicit_routes=routes)
                self.assertEqual(report.started, ("peer",) if phase == "timeout" else ("first", "peer"))
                self.assertEqual(report.outcome_unknown, ("first",) if phase == "timeout" else ())
                self.assertEqual(report.not_ready, ("last",))
                selected = [document["parts"][0], document["parts"][2]]
                self.assertEqual(workers, selected)
                self.assertEqual([call["part"] for call in hub.calls], selected)
                self.assertEqual(router.calls, [("first", None), ("peer", HIGH)])
                self.assertEqual([call["route"] for call in hub.calls], [LOW, HIGH])
                self.assertEqual([call["worker"] for call in hub.calls],
                                 ["local-worker-first", "local-worker-peer"])
                for call in hub.calls:
                    self.assertEqual(call["key"], expected_key(document, call["part"]["id"]))
                retained = inspect_project(ledger, plan.project_id)
                self.assertEqual(retained["plan_digest"], pristine.digest)
                self.assertEqual(retained["blocked_queued_ids"], ["last"])
                self.assertEqual([part["state"] for part in retained["parts"]],
                                 ["outcome_unknown" if phase == "timeout" else "running", "queued", "running"])
                for wanted, saved in zip(document["parts"], retained["parts"]):
                    self.assertEqual({key: saved[key] for key in wanted}, wanted)
                if phase == "timeout":
                    evidence = retained["parts"][0]["evidence"]
                    self.assertEqual(evidence["locator"], expected_key(document, "first"))
                    self.assertIn("TimeoutError", evidence["finding"])
                events = ledger.events(plan.project_id)
                repeated = dispatch_ready(pristine, ledger, hub, router, worker_for=worker_for,
                                          explicit_routes={"peer": HIGH})
                self.assertEqual(repeated.started, ())
                self.assertEqual(repeated.outcome_unknown, ())
                self.assertEqual(repeated.not_ready, ("last",))
                self.assertEqual(len(hub.calls), 2)
                self.assertEqual(ledger.events(plan.project_id), events)
            before_read = path.read_bytes()
            with Ledger.open_readonly(path) as ledger:
                self.assertEqual(inspect_project(ledger, plan.project_id), retained)
            self.assertEqual(path.read_bytes(), before_read)
        if phase is None:
            self.assertEqual(plan.to_dict(), document)
        else:
            self.assertEqual(changed, [phase])
            self.assertNotEqual(plan.to_dict(), document)

    def test_unchanged_native_fields_keep_order_keys_and_state(self):
        self.run_callback_case(None)

    def test_worker_router_and_receipt_callbacks_use_captured_parts(self):
        for phase in ("worker", "router", "receipt"):
            with self.subTest(phase=phase):
                self.run_callback_case(phase)

    def test_hub_callback_preserves_accepted_and_unknown_identity(self):
        for phase in ("hub", "timeout"):
            with self.subTest(phase=phase):
                self.run_callback_case(phase)

    def test_route_mapping_callback_cannot_change_the_captured_plan(self):
        self.run_callback_case("routes")

    def test_stale_entry_is_refused_without_workers_routes_or_writes(self):
        for recorded in (False, True):
            with self.subTest(recorded=recorded), Ledger() as ledger:
                sources, plan = authored_plan()
                if recorded:
                    ledger.record_plan(plan)
                before = ledger.project_snapshot(plan.project_id)
                events = ledger.events(plan.project_id)
                statements = []
                ledger._db.set_trace_callback(statements.append)
                sources[1].instruction = "Changed after validation."
                workers, hub, router = [], LocalHub(), ObservedRouter()

                def worker_for(part):
                    workers.append(part.id)
                    return "local-worker"

                with self.assertRaisesRegex(LedgerError, "changed since validation"):
                    dispatch_ready(plan, ledger, hub, router, worker_for=worker_for)
                self.assertEqual(workers, [])
                self.assertEqual(router.calls, [])
                self.assertEqual(hub.calls, [])
                self.assertEqual(ledger.project_snapshot(plan.project_id), before)
                self.assertEqual(ledger.events(plan.project_id), events)
                self.assertFalse(any(sql.upper().startswith("BEGIN") for sql in statements))

    def test_custom_plan_keeps_readiness_serialization_and_key_methods(self):
        class CustomPlan(Plan):
            def to_dict(self):
                document = super().to_dict()
                document["parts"].reverse()
                return document

            def idempotency_key(self, part_id):
                return "custom-" + super().idempotency_key(part_id)

            def ready_parts(self, completed=()):
                return tuple(part for part in super().ready_parts(completed) if part.id == "peer")

        _, source = authored_plan()
        plan = CustomPlan(source.project_id, native_plan(source.to_dict()).parts)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            with Ledger(str(path)) as ledger:
                hub, router = LocalHub(), ObservedRouter()
                report = dispatch_ready(plan, ledger, hub, router, worker_for=lambda part: "local-custom")
                self.assertEqual(report.started, ("peer",))
                self.assertEqual(report.not_ready, ("first", "last"))
                self.assertEqual([call["part"]["id"] for call in hub.calls], ["peer"])
                self.assertEqual(hub.calls[0]["key"], plan.idempotency_key("peer"))
            with Ledger.open_readonly(path) as ledger:
                snapshot = ledger.project_snapshot(plan.project_id)
                self.assertEqual(json.loads(snapshot["plan_json"]), plan.to_dict())
                self.assertEqual(snapshot["plan_digest"], plan.digest)
                for row in snapshot["parts"]:
                    self.assertEqual(row["idempotency_key"], plan.idempotency_key(row["part_id"]))


if __name__ == "__main__":
    unittest.main()
