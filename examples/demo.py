"""Local-only example; no remote services are contacted."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready


class LocalHub:
    def submit(self, part, *, route, worker_id, idempotency_key):
        print(f"accepted {part.id} on {worker_id} at {route.model}/{route.effort}")
        return {"task_id": "local-" + part.id}


plan = Plan.from_dict({
    "project": "demo",
    "parts": [
        {"id": "research", "instruction": "Collect three public references."},
        {"id": "write", "instruction": "Draft a short result.", "depends_on": ["research"]},
    ],
})
router = EffortRouter(
    {"model-a": ("low", "high"), "model-b": ("low", "high")},
    pool=(Route("model-a", "low"), Route("model-b", "low")),
    step_up=Route("model-b", "high"),
)
with Ledger(":memory:") as ledger:
    result = dispatch_ready(plan, ledger, LocalHub(), router, worker_for=lambda _: "worker-a")
    print("started:", ", ".join(result.started))
    print("waiting on prerequisites:", ", ".join(result.not_ready))
