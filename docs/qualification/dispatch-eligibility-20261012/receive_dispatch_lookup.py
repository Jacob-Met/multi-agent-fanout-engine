"""Independent local consumer for fan-out dispatch lookup qualification.

Imports one explicitly supplied source directory. All adapters are local fakes;
all databases are temporary. Timing includes the complete dispatch_ready call.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import statistics
import sys
import tempfile
import time


def fingerprint(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project

    catalog = {"local-a": ("low", "high"), "local-b": ("medium",)}
    router = EffortRouter(catalog, pool=(Route("local-a", "low"), Route("local-b", "medium")))
    evidence = {"source": "local fixture", "locator": "fixture-only", "finding": "authored outcome"}

    def capture(ledger, plan, calls, reports):
        snapshot = inspect_project(ledger, plan.project_id)
        for part in snapshot["parts"]:
            part.pop("updated_at", None)
        events = ledger.events(plan.project_id)
        for event in events:
            event.pop("at", None)
        return {"snapshot": snapshot, "events": events, "calls": calls,
                "reports": [asdict(report) for report in reports]}

    def mark_running(ledger, plan, part_id):
        ledger.mark_dispatching(plan.project_id, part_id, "external-local", {"model": "local-a", "effort": "high"})
        ledger.mark_running(plan.project_id, part_id, "external-" + part_id)

    cases = {}
    with tempfile.TemporaryDirectory(prefix="fanout-independent-") as scratch:
        path = str(Path(scratch) / "mixed.sqlite")
        plan = Plan.from_dict({"project": "mixed", "parts": [
            {"id": "starter", "instruction": "Local first task"},
            {"id": "sibling", "instruction": "Changed by adapter before its turn"},
            {"id": "failed", "instruction": "Retained failed task"},
            {"id": "unknown", "instruction": "Retained unknown task"},
            {"id": "running", "instruction": "Retained accepted task"},
            {"id": "dispatching", "instruction": "Retained in-flight task"},
            {"id": "completed", "instruction": "Retained completion"},
            {"id": "afterStarter", "instruction": "Next-call readiness", "depends_on": ["starter"]},
            {"id": "afterCompleted", "instruction": "Initially ready dependency", "depends_on": ["completed"]},
        ]})
        calls = []
        with Ledger(path) as ledger:
            ledger.record_plan(plan)
            for part_id in ("failed", "unknown", "running", "completed"):
                mark_running(ledger, plan, part_id)
            for part_id in ("failed", "unknown"):
                ledger.mark_outcome_unknown(plan.project_id, part_id, evidence)
            ledger.reconcile_unknown(plan.project_id, "failed", verdict="failed", evidence=evidence)
            ledger.mark_completed(plan.project_id, "completed", "artifact://local-completed", evidence)
            ledger.mark_dispatching(plan.project_id, "dispatching", "external-local", {"model": "local-a", "effort": "low"})

            class MixedHub:
                def submit(self, part, *, route, worker_id, idempotency_key):
                    calls.append([part.id, asdict(route), worker_id, idempotency_key])
                    if part.id == "starter":
                        mark_running(ledger, plan, "sibling")
                    return {"task_id": "accepted-" + part.id}

            hub = MixedHub()
            first = dispatch_ready(plan, ledger, hub, router, worker_for=lambda part: "worker-" + part.id)
            assert first.started == ("starter", "afterCompleted"), first
            assert first.not_ready == ("afterStarter",), first
            ledger.mark_completed(plan.project_id, "starter", "artifact://starter", evidence)
            second = dispatch_ready(plan, ledger, hub, router, worker_for=lambda part: "worker-" + part.id)
            assert second.started == ("afterStarter",), second
            assert [call[0] for call in calls] == ["starter", "afterCompleted", "afterStarter"]
            cases["mixed_callback_two_waves"] = capture(ledger, plan, calls, [first, second])
        with Ledger(path) as reopened:
            prior_calls = list(calls)
            class NeverSubmit:
                def submit(self, *args, **kwargs):
                    raise AssertionError("already dispatched task was replayed")
            final = dispatch_ready(plan, reopened, NeverSubmit(), router, worker_for=lambda part: "unused")
            assert not final.started and not final.outcome_unknown
            assert calls == prior_calls
            cases["reopened_no_replay"] = capture(reopened, plan, calls, [final])

    # In-loop external acceptance must also be noticed when an earlier adapter
    # fails ambiguously; no selected-set snapshot can authorize the later row.
    plan = Plan.from_dict({"project": "ambiguous", "parts": [
        {"id": "alpha", "instruction": "Raises after a local side effect"},
        {"id": "beta", "instruction": "Accepted by that local side effect"},
        {"id": "gamma", "instruction": "Independent remaining task"},
    ]})
    with Ledger() as ledger:
        calls = []
        class AmbiguousHub:
            def submit(self, part, *, route, worker_id, idempotency_key):
                calls.append([part.id, asdict(route), worker_id, idempotency_key])
                if part.id == "alpha":
                    mark_running(ledger, plan, "beta")
                    raise TimeoutError("local authored unknown")
                return {"task_id": "accepted-" + part.id}
        first = dispatch_ready(plan, ledger, AmbiguousHub(), router, worker_for=lambda _: "local")
        assert first.started == ("gamma",) and first.outcome_unknown == ("alpha",), first
        assert [call[0] for call in calls] == ["alpha", "gamma"]
        cases["ambiguous_callback"] = capture(ledger, plan, calls, [first])

    # Keep SQL instrumentation out of timing. This records query shape, not a
    # pretend count of rows returned by SQLite.
    plan = Plan.from_dict({"project": "query-shape", "parts": [
        {"id": "p" + str(i), "instruction": "Local probe"} for i in range(37)
    ]})
    with Ledger() as ledger:
        statements = []
        ledger._db.set_trace_callback(statements.append)
        class PlainHub:
            def submit(self, part, **kwargs):
                return {"task_id": "accepted-" + part.id}
        report = dispatch_ready(plan, ledger, PlainHub(), router, worker_for=lambda _: "local")
        assert len(report.started) == 37
        query_shape = {
            "queued_set_selects": sum("SELECT part_id FROM parts" in sql and "state='queued'" in sql for sql in statements),
            "indexed_part_selects": sum("SELECT * FROM parts WHERE project_id=" in sql and " AND part_id=" in sql for sql in statements),
        }

    benchmarks = []
    for storage in ("memory", "disk"):
        for count in (64, 512):
            plan = Plan.from_dict({"project": "bench", "parts": [
                {"id": "p" + str(i), "instruction": "Pure local benchmark task"} for i in range(count)
            ]})
            for registration in ("first", "pre_recorded"):
                timings = []
                signatures = []
                for _ in range(args.repeat):
                    with tempfile.TemporaryDirectory(prefix="fanout-bench-") as scratch:
                        database = ":memory:" if storage == "memory" else str(Path(scratch) / "ledger.sqlite")
                        with Ledger(database) as ledger:
                            if registration == "pre_recorded":
                                ledger.record_plan(plan)
                            calls = []
                            class TimedHub:
                                def submit(self, part, *, route, worker_id, idempotency_key):
                                    calls.append([part.id, asdict(route), worker_id, idempotency_key])
                                    return {"task_id": "accepted-" + part.id}
                            started = time.perf_counter()
                            report = dispatch_ready(plan, ledger, TimedHub(), router, worker_for=lambda _: "local")
                            elapsed = time.perf_counter() - started
                            assert len(report.started) == count and not report.outcome_unknown and not report.not_ready
                            assert len(calls) == count
                            signatures.append(fingerprint(capture(ledger, plan, calls, [report])))
                            timings.append(elapsed)
                assert len(set(signatures)) == 1
                benchmarks.append({"storage": storage, "parts": count, "registration": registration,
                                   "seconds": timings, "median_seconds": statistics.median(timings),
                                   "consumer_sha256": signatures[0]})

    result = {"source": str(args.source.resolve()), "python": platform.python_version(),
              "sqlite": sqlite3.sqlite_version, "platform": platform.platform(),
              "external_provider_calls": 0, "cases": cases, "cases_sha256": fingerprint(cases),
              "query_shape": query_shape, "benchmarks": benchmarks,
              "limits": ["Synthetic local adapters only; no remote dispatch or production throughput measured.",
                         "Timings include full dispatch_ready; source import and Ledger construction are outside the timer.",
                         "Disk uses temporary SQLite with the native default journal and synchronous settings.",
                         "Shared-host timing is descriptive, not a universal speed guarantee."]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"cases_sha256": result["cases_sha256"], "query_shape": query_shape,
                      "benchmarks": benchmarks}, indent=2))


if __name__ == "__main__":
    main()
