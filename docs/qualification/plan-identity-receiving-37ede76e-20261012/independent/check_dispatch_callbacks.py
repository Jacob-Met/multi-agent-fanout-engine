"""Independent public-API receiving for dispatch capture at PR49.

Uses only local adapters and in-memory SQLite. Checks remain active under -O.
Run against one archived source root, not an installed project.
"""
from __future__ import annotations
import copy
import json
import pathlib
import sys
import traceback
from collections.abc import Mapping

sys.path.insert(0, str(pathlib.Path(sys.argv[1]).resolve()))
from fanout_engine import Part, Plan, Ledger, LedgerError, Route, EffortRouter, dispatch_ready

CASES = []
ROUTE = Route("receiving-model", "high")


class MutablePart:
    def __init__(self, part_id, instruction, depends_on=(), tags=()):
        self.id = part_id
        self.instruction = instruction
        self.depends_on = list(depends_on)
        self.tags = list(tags)

    def to_dict(self):
        return {"id": self.id, "instruction": self.instruction,
                "depends_on": list(self.depends_on), "tags": list(self.tags)}


class Case:
    def __init__(self, name):
        self.data = {"name": name, "checks": 0, "failures": [], "observations": {}}
        CASES.append(self.data)

    def check(self, label, actual, expected=True):
        self.data["checks"] += 1
        if actual != expected:
            self.data["failures"].append(
                {"check": label, "actual": actual, "expected": expected})

    def error(self, label, exc):
        return {"stage": label, "type": type(exc).__name__, "message": str(exc),
                "traceback": traceback.format_exc()}


class ObservedLedger(Ledger):
    def __init__(self):
        super().__init__()
        self.received_plans = []

    def record_plan(self, plan):
        self.received_plans.append(plan)
        return super().record_plan(plan)


def router():
    return EffortRouter({"receiving-model": ("high",)}, pool=(ROUTE,))


def native_from_document(document):
    return Plan(document["project"], tuple(
        Part(p["id"], p["instruction"], p["depends_on"], p["tags"])
        for p in document["parts"]
    ))


def multi_part(stage, uncertain):
    case = Case("multi_part/" + stage + ("/uncertain" if uncertain else "/accepted"))
    first = MutablePart("first", "Approved first", tags=("red", "red", "blue"))
    blocked = MutablePart("blocked", "Approved blocked",
                          depends_on=("last", "first"), tags=("keep", "keep"))
    stable = Part("stable", "Approved native", tags=("native", "native"))
    last = MutablePart("last", "Approved last", tags=("last",))
    plan = Plan("receive-" + stage + ("-unknown" if uncertain else "-accepted"),
                (first, blocked, stable, last))
    approved = copy.deepcopy(plan.to_dict())
    expected = {p["id"]: p for p in approved["parts"]}
    keys = {p["id"]: plan.idempotency_key(p["id"]) for p in approved["parts"]}
    digest = plan.digest
    mutated = []
    workers = []
    routes = []
    submissions = []
    ledger = ObservedLedger()

    def mutate():
        if mutated:
            return
        mutated.append(stage)
        first.id = "first-edited"
        first.instruction = "Changed first from callback"
        first.tags[:] = ["changed"]
        blocked.id = "blocked-edited"
        blocked.instruction = "Changed blocked from callback"
        blocked.depends_on.clear()
        blocked.tags[:] = ["changed"]
        last.id = "last-edited"
        last.instruction = "Changed later ready from callback"
        last.depends_on[:] = ["first-edited"]
        last.tags[:] = ["changed"]

    def worker_for(part):
        if stage == "worker" and not mutated:
            mutate()
        workers.append({"payload": copy.deepcopy(part.to_dict()),
                        "is_original_native": part is stable})
        return "worker-" + part.id

    class CallbackRouter(EffortRouter):
        def route_for(self, part_id, explicit=None):
            if stage == "router" and not mutated:
                mutate()
            routes.append(part_id)
            return super().route_for(part_id, explicit)

    class Response(dict):
        def get(self, key, default=None):
            if stage == "response" and not mutated:
                mutate()
                if uncertain:
                    raise OSError("local response uncertainty witness")
            return super().get(key, default)

    class LocalHub:
        def submit(self, part, *, route, worker_id, idempotency_key):
            first_call = len(submissions) == 0
            if stage == "hub" and not mutated:
                mutate()
            submissions.append({"payload": copy.deepcopy(part.to_dict()),
                                "key": idempotency_key, "worker": worker_id,
                                "route": {"model": route.model, "effort": route.effort},
                                "is_original_native": part is stable})
            if first_call and uncertain and stage != "response":
                raise OSError("local submit uncertainty witness")
            return Response(task_id="task-" + part.id)

    report = None
    error = None
    try:
        report = dispatch_ready(
            plan, ledger, LocalHub(),
            CallbackRouter({"receiving-model": ("high",)}, pool=(ROUTE,)),
            worker_for=worker_for,
        )
    except Exception as exc:
        error = case.error("first dispatch", exc)
    case.check("dispatch completes without escaping callback mutation", error, None)
    case.check("caller sources really changed", bool(mutated))
    case.check("caller current source stays edited", first.id, "first-edited")
    case.check("caller later-ready source stays edited", last.id, "last-edited")
    case.check("caller blocked source stays edited", blocked.id, "blocked-edited")
    actual_report = None if report is None else {
        "started": list(report.started), "outcome_unknown": list(report.outcome_unknown),
        "not_ready": list(report.not_ready)}
    expected_report = {"started": ["stable", "last"] if uncertain else ["first", "stable", "last"],
                       "outcome_unknown": ["first"] if uncertain else [],
                       "not_ready": ["blocked"]}
    case.check("report uses approved identities and outcomes", actual_report, expected_report)
    case.check("worker callbacks see approved ready order",
               [w["payload"]["id"] for w in workers], ["first", "stable", "last"])
    case.check("router callbacks see approved ready order", routes, ["first", "stable", "last"])
    case.check("Hub receives approved ready order",
               [s["payload"]["id"] for s in submissions], ["first", "stable", "last"])
    for part_id in ("first", "stable", "last"):
        sent = [s for s in submissions if s["payload"]["id"] == part_id]
        case.check(part_id + " submitted exactly once", len(sent), 1)
        if len(sent) == 1:
            case.check(part_id + " exact approved payload", sent[0]["payload"], expected[part_id])
            case.check(part_id + " approved recorded key", sent[0]["key"], keys[part_id])
    case.check("mixed native Part identity reaches worker",
               [w["is_original_native"] for w in workers if w["payload"]["id"] == "stable"], [True])
    case.check("mixed native Part identity reaches Hub",
               [s["is_original_native"] for s in submissions if s["payload"]["id"] == "stable"], [True])
    snapshot = ledger.project_snapshot(plan.project_id)
    case.check("recorded document remains approved",
               None if snapshot is None else json.loads(snapshot["plan_json"]), approved)
    case.check("recorded plan digest remains approved",
               None if snapshot is None else snapshot["plan_digest"], digest)
    rows = {} if snapshot is None else {p["part_id"]: p for p in snapshot["parts"]}
    expected_states = {"first": "outcome_unknown" if uncertain else "running",
                       "stable": "running", "last": "running", "blocked": "queued"}
    case.check("all approved rows have correct states",
               {p: r["state"] for p, r in rows.items()}, expected_states)
    for part_id in expected:
        row = rows.get(part_id)
        case.check(part_id + " ledger payload preserved",
                   None if row is None else json.loads(row["payload_json"]), expected[part_id])
        case.check(part_id + " ledger key preserved",
                   None if row is None else row["idempotency_key"], keys[part_id])
    if error is None:
        events_before = ledger.events(plan.project_id)
        calls_before = copy.deepcopy(submissions)
        retry_error = None
        retry_report = None
        try:
            retry_report = dispatch_ready(native_from_document(approved), ledger,
                                          LocalHub(), router(), worker_for=worker_for)
        except Exception as exc:
            retry_error = case.error("repeat dispatch", exc)
        case.check("repeat dispatch returns normally", retry_error, None)
        case.check("repeat dispatch adds no Hub submissions", submissions, calls_before)
        case.check("repeat dispatch adds no ledger events", ledger.events(plan.project_id), events_before)
        case.check("repeat dispatch leaves running and unknown rows parked",
                   None if retry_report is None else
                   [list(retry_report.started), list(retry_report.outcome_unknown), list(retry_report.not_ready)],
                   [[], [], ["blocked"]])
        case.data["observations"]["repeat_error"] = retry_error
    case.data["observations"].update({
        "approved_document": approved, "approved_keys": keys, "mutated_at": mutated,
        "workers": workers, "routes": routes, "submissions": submissions,
        "report": actual_report, "states": {p: r["state"] for p, r in rows.items()},
        "error": error,
    })
    ledger.close()


def mapping_entry():
    case = Case("explicit_routes_mapping_callback")
    mutable = MutablePart("legacy", "Approved mapping payload", tags=("keep", "keep"))
    native = Part("native", "Approved native payload")
    plan = Plan("receive-mapping", (mutable, native))
    approved = copy.deepcopy(plan.to_dict())
    keys = {p.id: plan.idempotency_key(p.id) for p in plan.parts}
    mutation = []
    seen = []
    ledger = ObservedLedger()

    class Routes(Mapping):
        def __iter__(self):
            mutation.append("mapping.__iter__")
            mutable.instruction = "Mapping changed caller source"
            mutable.tags[:] = ["changed"]
            return iter(("legacy",))

        def __len__(self):
            return 1

        def __getitem__(self, key):
            if key != "legacy":
                raise KeyError(key)
            return ROUTE

    class Hub:
        def submit(self, part, *, route, worker_id, idempotency_key):
            seen.append({"payload": copy.deepcopy(part.to_dict()), "key": idempotency_key,
                         "native_identity": part is native})
            return {"task_id": "task-" + part.id}

    error = None
    report = None
    try:
        report = dispatch_ready(plan, ledger, Hub(), router(),
                                worker_for=lambda p: "worker-" + p.id, explicit_routes=Routes())
    except Exception as exc:
        error = case.error("mapping dispatch", exc)
    case.check("mapping course returns normally", error, None)
    case.check("mapping callback executed", mutation, ["mapping.__iter__"])
    case.check("mapping edit remains on caller", mutable.instruction, "Mapping changed caller source")
    case.check("mapping edit cannot change submitted approved payloads",
               [s["payload"] for s in seen], approved["parts"])
    case.check("mapping course retains approved keys",
               [s["key"] for s in seen], [keys["legacy"], keys["native"]])
    case.check("mapping course retains mixed native identity",
               [s["native_identity"] for s in seen], [False, True])
    snapshot = ledger.project_snapshot(plan.project_id)
    case.check("mapping edit cannot change admitted document",
               None if snapshot is None else json.loads(snapshot["plan_json"]), approved)
    case.check("mapping report accepts original IDs",
               None if report is None else list(report.started), ["legacy", "native"])
    case.data["observations"] = {"error": error, "submissions": seen, "mutation": mutation}
    ledger.close()


def custom_plan():
    case = Case("custom_plan_public_contracts")
    class CustomPlan(Plan):
        def to_dict(self):
            value = super().to_dict()
            value["parts"].reverse()
            return value

        def idempotency_key(self, part_id):
            return "custom-" + super().idempotency_key(part_id)

        def ready_parts(self, completed=()):
            return (self.parts[-1],)

    a, b = Part("a", "First custom"), Part("b", "Last custom")
    plan = CustomPlan("receive-custom", (a, b))
    approved = copy.deepcopy(plan.to_dict())
    key = plan.idempotency_key("b")
    seen, workers = [], []
    ledger = ObservedLedger()

    def worker(part):
        workers.append(part is b)
        return "worker-b"

    class Hub:
        def submit(self, part, *, route, worker_id, idempotency_key):
            seen.append({"part_is_b": part is b, "key": idempotency_key,
                         "payload": copy.deepcopy(part.to_dict())})
            return {"task_id": "custom-task"}

    report = dispatch_ready(plan, ledger, Hub(), router(), worker_for=worker)
    snapshot = ledger.project_snapshot(plan.project_id)
    case.check("custom Plan object reaches Ledger unchanged", ledger.received_plans[0] is plan)
    case.check("custom serialized document remains exact", json.loads(snapshot["plan_json"]), approved)
    case.check("custom readiness override is honored",
               [list(report.started), list(report.outcome_unknown), list(report.not_ready)], [["b"], [], ["a"]])
    case.check("custom idempotency key reaches Hub", [s["key"] for s in seen], [key])
    case.check("custom idempotency key remains recorded", ledger.idempotency_key(plan.project_id, "b"), key)
    case.check("custom native Part identity reaches worker", workers, [True])
    case.check("custom native Part identity reaches Hub", [s["part_is_b"] for s in seen], [True])
    case.check("custom unselected part remains queued", ledger.part_state(plan.project_id, "a"), "queued")
    case.data["observations"] = {"document": approved, "submissions": seen}
    ledger.close()


def native_identity():
    case = Case("all_native_object_identity")
    parts = (Part("a", "Native A"), Part("b", "Native B"))
    plan = Plan("receive-native", parts)
    ledger = ObservedLedger()
    workers, submitted = [], []
    def worker(part):
        workers.append(part)
        return "worker-" + part.id
    class Hub:
        def submit(self, part, *, route, worker_id, idempotency_key):
            submitted.append(part)
            return {"task_id": "task-" + part.id}
    report = dispatch_ready(plan, ledger, Hub(), router(), worker_for=worker)
    case.check("all-native Plan identity reaches Ledger", ledger.received_plans[0] is plan)
    case.check("all-native worker identity and order", [p is q for p, q in zip(workers, parts)], [True, True])
    case.check("all-native Hub identity and order", [p is q for p, q in zip(submitted, parts)], [True, True])
    case.check("all-native worker count", len(workers), 2)
    case.check("all-native submission count", len(submitted), 2)
    case.check("all-native accepted report", list(report.started), ["a", "b"])
    ledger.close()


def stale_before_entry():
    case = Case("stale_source_before_entry")
    mutable = MutablePart("stale", "Originally approved")
    plan = Plan("receive-stale", (mutable,))
    mutable.instruction = "Changed before dispatch admission"
    ledger = ObservedLedger()
    calls = []
    def worker(part):
        calls.append("worker")
        return "worker-stale"
    class Hub:
        def submit(self, part, **kwargs):
            calls.append("Hub")
            return {"task_id": "task-stale"}
    error = None
    try:
        dispatch_ready(plan, ledger, Hub(), router(), worker_for=worker)
    except Exception as exc:
        error = case.error("stale entry", exc)
    case.check("stale payload fails at admission with LedgerError",
               None if error is None else error["type"], "LedgerError")
    case.check("stale admission invokes no worker or Hub callbacks", calls, [])
    case.check("stale admission leaves no stored project", ledger.project_snapshot(plan.project_id), None)
    case.check("stale admission leaves no ledger events", ledger.events(plan.project_id), [])
    case.check("stale admission does not call Ledger.record_plan", len(ledger.received_plans), 0)
    case.data["observations"] = {"error": error, "callbacks": calls}
    ledger.close()


for stage in ("worker", "router", "hub", "response"):
    for uncertain in (False, True):
        multi_part(stage, uncertain)
for control in (mapping_entry, custom_plan, native_identity, stale_before_entry):
    try:
        control()
    except Exception as exc:
        case = Case("unexpected_control_error/" + control.__name__)
        case.check("control executes fully", {"type": type(exc).__name__, "message": str(exc),
                                            "traceback": traceback.format_exc()}, None)

result = {
    "schema": "hamon.dispatch-callback-independent-profile.v1",
    "source_root": str(pathlib.Path(sys.argv[1]).resolve()),
    "python": sys.version, "optimize": sys.flags.optimize,
    "case_count": len(CASES), "checks": sum(c["checks"] for c in CASES),
    "failure_count": sum(len(c["failures"]) for c in CASES),
    "cases": CASES,
}
print(json.dumps(result, ensure_ascii=False, sort_keys=True))
raise SystemExit(1 if result["failure_count"] else 0)
