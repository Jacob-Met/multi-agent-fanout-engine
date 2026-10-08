"""Inspect an authored retained project locally; no adapter is connected."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fanout_engine import Ledger, Plan, inspect_project


def main() -> None:
    plan = Plan.from_dict({
        "project": "inspection-demo",
        "parts": [
            {"id": "research", "instruction": "Read authored sample references."},
            {"id": "draft", "instruction": "Prepare authored text."},
            {"id": "fetch", "instruction": "Retrieve local fixture material."},
            {"id": "verify", "instruction": "Check retrieved material.", "depends_on": ["fetch"]},
            {"id": "benchmark", "instruction": "Evaluate the authored control."},
            {"id": "signoff", "instruction": "Review evaluation.", "depends_on": ["benchmark"]},
            {"id": "publish", "instruction": "Prepare a local review artifact.",
             "depends_on": ["draft", "verify", "signoff"]},
            {"id": "notes", "instruction": "Prepare fixture notes."},
        ],
    })
    with Ledger(":memory:") as ledger:
        ledger.record_plan(plan)
        for name in ("research", "draft", "fetch", "benchmark"):
            ledger.mark_dispatching(plan.project_id, name, "local-worker",
                                    {"model": "model-a", "effort": "low"})
            ledger.mark_running(plan.project_id, name, "local-task-" + name)
        ledger.mark_completed(plan.project_id, "research", "local-artifact:references")
        evidence = {"source": "authored local example", "locator": "fixture:fetch",
                    "finding": "acceptance is intentionally unverified in this example"}
        ledger.mark_outcome_unknown(plan.project_id, "fetch", evidence)
        ledger.mark_outcome_unknown(plan.project_id, "benchmark",
                                    {**evidence, "locator": "fixture:benchmark"})
        ledger.reconcile_unknown(
            plan.project_id, "benchmark", verdict="failed",
            evidence={**evidence, "locator": "fixture:benchmark",
                      "finding": "authored failure control"},
        )
        # This consumer needs only the recorded project ID and existing ledger.
        print(json.dumps(inspect_project(ledger, "inspection-demo"),
                         indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
