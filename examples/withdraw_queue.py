"""Withdraw authored local work, reopen its ledger, and observe zero submissions."""
from dataclasses import asdict
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project


def run():
    plan = Plan.from_dict({"project": "local-withdrawal-demo", "parts": [
        {"id": "build", "instruction": "Produce an authored fixture."},
        {"id": "verify", "instruction": "Inspect it.", "depends_on": ["build"]},
    ]})
    evidence = {"source": "authored caller decision", "locator": "fixture:request/withdraw",
                "finding": "The fixture is no longer requested; no worker was submitted."}

    class LocalHub:
        def __init__(self):
            self.submissions = []

        def submit(self, part, **kwargs):
            self.submissions.append(part.id)
            return {"task_id": "local:" + part.id}

    with tempfile.TemporaryDirectory(prefix="fanout-withdrawal-") as directory:
        database = str(Path(directory) / "ledger.sqlite3")
        with Ledger(database) as ledger:
            ledger.record_plan(plan)
            ledger.withdraw_queued(plan.project_id, "build", evidence)
        with Ledger(database) as reopened:
            hub = LocalHub()
            router = EffortRouter({"fixture": ("low",)}, pool=(Route("fixture", "low"),))
            result = dispatch_ready(plan, reopened, hub, router, worker_for=lambda part: "local-worker")
            return {"submissions": hub.submissions, "dispatch": asdict(result),
                    "events": [event["event"] for event in reopened.events(plan.project_id, "build")],
                    "project": inspect_project(reopened, plan.project_id)}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True, indent=2))
