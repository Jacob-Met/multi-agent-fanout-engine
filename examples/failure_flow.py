"""Record a real authored local child failure; no remote adapter is connected."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project
from fanout_engine.inspect import _write_stdout


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


def _run_example(database: Path | None):
    plan = Plan.from_dict({"project": "local-failure-demo", "parts": [
        {"id": "build", "instruction": "Run an authored failing local fixture."},
        {"id": "verify", "instruction": "Inspect the fixture output.", "depends_on": ["build"]},
    ]})
    router = EffortRouter({"local-fixture": ("low",)}, pool=(Route("local-fixture", "low"),))
    hub = LocalFailureHub()
    try:
        with Ledger(str(database.absolute()) if database is not None else ":memory:") as ledger:
            first = dispatch_ready(plan, ledger, hub, router, worker_for=lambda part: "local-example")
            if hub.process is None:
                raise RuntimeError("local child was not accepted")
            stdout, stderr = hub.process.communicate(timeout=10)
            if hub.process.returncode != 7:
                raise RuntimeError("authored failure control returned an unexpected status")
            ledger.mark_failed(plan.project_id, "build", {
                "source": "authored local subprocess",
                "locator": f"local-child:{hub.process.pid}",
                "finding": f"observed terminal exit {hub.process.returncode}: {stderr.strip()}",
            })
            next_dispatch = dispatch_ready(plan, ledger, hub, router, worker_for=lambda part: "local-example")
            report = {"first_dispatch": asdict(first),
                      "next_dispatch": asdict(next_dispatch),
                      "local_submissions": hub.submissions,
                      "child_returncode": hub.process.returncode,
                      "child_stdout": stdout, "child_stderr": stderr,
                      "events": ledger.events(plan.project_id, "build"),
                      "project": inspect_project(ledger, plan.project_id)}
        if database is not None:
            with Ledger.open_readonly(database) as retained:
                report["events"] = retained.events(plan.project_id, "build")
                report["project"] = inspect_project(retained, plan.project_id)
        return report
    finally:
        if hub.process is not None and hub.process.poll() is None:
            hub.process.kill()
            hub.process.communicate()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--database", type=Path,
                        help="retain this example in a new SQLite file; its parent must already exist")
    args = parser.parse_args(argv)
    created = False
    try:
        if args.database is not None:
            args.database.touch(exist_ok=False)
            created = True
        report = _run_example(args.database)
        _write_stdout((json.dumps(report, indent=2) + "\n").encode("utf-8"))
        return 0
    except KeyboardInterrupt:
        print("failure example: interrupted", file=sys.stderr)
        code = 130
    except (OSError, sqlite3.Error, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"failure example: {exc}", file=sys.stderr)
        code = 2
    if created:
        print(f"Example database retained at {args.database}; inspect it before using its partial results.",
              file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
