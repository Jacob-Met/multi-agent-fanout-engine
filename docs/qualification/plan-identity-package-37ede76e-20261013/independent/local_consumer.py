"""One authored persistent public-API consumer for the relocated fanout package."""
import hashlib
import json
from pathlib import Path
import sys

repo = Path(sys.argv[1]).resolve()
database = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(repo))
from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project

def check(condition, message):
    if not condition:
        raise RuntimeError(message)

check(sys.flags.isolated == 1 and sys.dont_write_bytecode, "Isolated no-bytecode profile required")
check(not database.exists(), "Consumer database must be fresh")
calls = []
class LocalHub:
    def submit(self, part, *, route, worker_id, idempotency_key):
        calls.append({
            "part_id": part.id, "instruction": part.instruction,
            "worker_id": worker_id, "model": route.model,
            "effort": route.effort, "idempotency_key": idempotency_key,
        })
        return {"task_id": "local-receiving-" + part.id}

plan = Plan.from_dict({
    "project": "relocated-receiving",
    "parts": [
        {"id": "stage", "instruction": "Retain the authored local package receipt."},
        {"id": "verify", "instruction": "Inspect the completed local receipt.",
         "depends_on": ["stage"]},
    ],
})
router = EffortRouter({"local-model": ("low",)}, pool=(Route("local-model", "low"),))
with Ledger(str(database)) as ledger:
    first = dispatch_ready(plan, ledger, LocalHub(), router,
                           worker_for=lambda part: "local-worker")
    second = dispatch_ready(plan, ledger, LocalHub(), router,
                            worker_for=lambda part: "local-worker")
    check(first.started == ("stage",) and first.not_ready == ("verify",),
          "Unexpected initial dispatch readiness")
    check(first.outcome_unknown == () and second.outcome_unknown == (),
          "Unexpected ambiguous outcome")
    check(second.started == () and second.not_ready == ("verify",),
          "A retained running task was replayed or dependency readiness changed")
    check(len(calls) == 1, "Expected one local adapter submission")
    check(calls[0] == {
        "part_id": "stage", "instruction": "Retain the authored local package receipt.",
        "worker_id": "local-worker", "model": "local-model", "effort": "low",
        "idempotency_key": plan.idempotency_key("stage"),
    }, "Public route/payload/key disagreement")
    report = inspect_project(ledger, plan.project_id)
    check([(part["id"], part["state"]) for part in report["parts"]]
          == [("stage", "running"), ("verify", "queued")], "Retained states differ")
    check(report["queued_ready_ids"] == [] and report["blocked_queued_ids"] == ["verify"],
          "Retained dependency report differs")

modules = {}
for name, module in sorted(sys.modules.items()):
    if name == "fanout_engine" or name.startswith("fanout_engine."):
        path = Path(module.__file__).resolve()
        relative = path.relative_to(repo).as_posix()
        data = path.read_bytes()
        modules[name] = {
            "path": str(path), "relative_path": relative,
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(),
        }
check("fanout_engine.dispatch" in modules and "fanout_engine.ledger" in modules,
      "Public source provenance incomplete")
data = database.read_bytes()
print(json.dumps({
    "accepted": True,
    "plan_digest": plan.digest,
    "calls": calls,
    "first": {"started": first.started, "not_ready": first.not_ready},
    "second": {"started": second.started, "not_ready": second.not_ready},
    "report": report,
    "database": {"path": str(database), "bytes": len(data),
                 "sha256": hashlib.sha256(data).hexdigest()},
    "imported_modules": modules,
    "isolated": sys.flags.isolated,
    "dont_write_bytecode": sys.dont_write_bytecode,
}, indent=2, sort_keys=True))
