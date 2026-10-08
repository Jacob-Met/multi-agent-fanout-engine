#!/usr/bin/env python3
"""Distinct native consumer oracle, frozen without seeing preview source/tests."""
import json
from pathlib import Path
import sys


def no_effects(event, args):
    if event in {"sqlite3.connect", "socket.__new__", "subprocess.Popen", "os.system"}:
        raise AssertionError("forbidden preview effect: " + event)


sys.addaudithook(no_effects)
from fanout_engine.plan import Plan, strict_json_loads
from fanout_engine.routing import EffortRouter, Route
from fanout_engine.preview import preview_plan

fixture = Path(sys.argv[1])
expected = json.loads((fixture / "expected.json").read_bytes())["helper"]
raw_plan = (fixture / "fixture-plan.json").read_bytes()
routing = json.loads((fixture / "fixture-routes.json").read_bytes())
plan = Plan.from_dict(strict_json_loads(raw_plan.decode("utf-8")))
calls = []


class ObservedRouter(EffortRouter):
    def route_for(self, part_id, explicit=None):
        calls.append([part_id, None if explicit is None else {"model": explicit.model, "effort": explicit.effort}])
        return super().route_for(part_id, explicit)

    def step_up_after_refusal(self, *args, **kwargs):
        raise AssertionError("preview attempted an execution-time step-up")


router = ObservedRouter(routing["catalog"], pool=[Route(**v) for v in routing["pool"]], step_up=Route(**routing["step_up"]))
explicit = {key: Route(**value) for key, value in routing["explicit_routes"].items()}
before = {"plan": plan.to_dict(), "digest": plan.digest, "pool": router.pool,
          "step_up": router.step_up, "catalog": dict(router._catalog), "explicit": dict(explicit)}
report = preview_plan(plan, router, explicit_routes=explicit)
assert report == expected, {"expected": expected, "actual": report}
assert calls == [[part["id"], routing["explicit_routes"].get(part["id"])] for part in expected["plan"]["parts"]]
assert plan.digest == expected["plan_digest"]
assert [part.id for part in plan.ready_parts(())] == ["scan", "side"]
assert [plan.idempotency_key(part["id"]) for part in expected["plan"]["parts"]] == [r["idempotency_key"] for r in report["routes"]]
refusals = []
for label, overrides in [
    ("unknown-part", {"not-authored": Route("cpu-a", "low")}),
    ("non-route", {"pack": {"model": "gpu-b", "effort": "medium"}}),
    ("blocked-unauthorized-route", {"pack": Route("review-c", "high")}),
]:
    try:
        preview_plan(plan, router, explicit_routes=overrides)
    except (TypeError, ValueError) as exc:
        refusals.append({"case": label, "exception": type(exc).__name__, "message": str(exc)})
    else:
        raise AssertionError("invalid explicit route returned a success report: " + label)
after = {"plan": plan.to_dict(), "digest": plan.digest, "pool": router.pool,
         "step_up": router.step_up, "catalog": dict(router._catalog), "explicit": dict(explicit)}
assert before == after
print(json.dumps({"result": "ACCEPT", "report": report, "positive_route_calls": calls[:6],
                  "native_refusals": refusals, "native_objects_unchanged": True,
                  "effects": {"sqlite_connections": 0, "sockets": 0, "child_launches": 0, "step_up_calls": 0}},
                 sort_keys=True, ensure_ascii=False))
