"""Record a real authored local child failure; no remote adapter is connected."""
from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project


class LocalFailureHub:
    """One local child is enough to demonstrate accepted then failed work."""
    process: subprocess.Popen | None = None
    submissions = 0

    def submit(self, part, **kwargs):
        if part.id != "build" or self.process is not None:
            raise RuntimeError("example unexpectedly attempted another child")
        self.process = subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.stderr.write('authored fixture failure\\n'); sys.exit(7)"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.submissions += 1
        return {"task_id": f"local-child:{self.process.pid}"}


def main():
    plan = Plan.from_dict({"project": "local-failure-demo", "parts": [
        {"id": "build", "instruction": "Run an authored failing local fixture."},
        {"id": "verify", "instruction": "Inspect the fixture output.", "depends_on": ["build"]},
    ]})
    router = EffortRouter({"local-fixture": ("low",)}, pool=(Route("local-fixture", "low"),))
    hub = LocalFailureHub()
    with Ledger() as ledger:
        first = dispatch_ready(plan, ledger, hub, router, worker_for=lambda part: "local-example")
        if hub.process is None:
            raise RuntimeError("local child was not accepted")
        try:
            stdout, stderr = hub.process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            hub.process.kill()
            hub.process.communicate()
            raise
        if hub.process.returncode != 7:
            raise RuntimeError("authored failure control returned an unexpected status")
        ledger.mark_failed(plan.project_id, "build", {
            "source": "authored local subprocess",
            "locator": f"local-child:{hub.process.pid}",
            "finding": f"observed terminal exit {hub.process.returncode}: {stderr.strip()}",
        })
        next_dispatch = dispatch_ready(plan, ledger, hub, router, worker_for=lambda part: "local-example")
        print(json.dumps({"first_dispatch": asdict(first),
                          "next_dispatch": asdict(next_dispatch),
                          "local_submissions": hub.submissions,
                          "child_returncode": hub.process.returncode,
                          "child_stdout": stdout, "child_stderr": stderr,
                          "events": ledger.events(plan.project_id, "build"),
                          "project": inspect_project(ledger, plan.project_id)}, indent=2))


if __name__ == "__main__":
    main()
