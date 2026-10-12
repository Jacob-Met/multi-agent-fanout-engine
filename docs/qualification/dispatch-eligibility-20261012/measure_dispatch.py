#!/usr/bin/env python3
"""Compare complete local SQLite dispatch workflows from two source checkouts.

No provider calls are made. Each measured course uses a new temporary database,
accepts every independent part through a local adapter, closes/reopens/inspects
the ledger, and performs a second dispatch pass that must submit nothing.
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
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import perf_counter


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def stable_digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def receive_one(source, count):
    sys.path.insert(0, str(source))
    from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project

    calls = []

    class LocalHub:
        def submit(self, part, *, route, worker_id, idempotency_key):
            calls.append((part.id, route.model, route.effort, worker_id, idempotency_key))
            return {"task_id": "fixture-" + part.id}

    with TemporaryDirectory(prefix="fanout-eligibility-") as directory:
        database = str(Path(directory) / "ledger.sqlite")
        began = perf_counter()
        plan = Plan.from_dict({"project": "dispatch-cost", "parts": [
            {"id": f"part_{index:05d}", "instruction": "Accept this local fixture part."}
            for index in range(count)
        ]})
        router = EffortRouter({"model-a": ("low",), "model-b": ("low",)},
                              pool=(Route("model-a", "low"), Route("model-b", "low")))
        with Ledger(database) as ledger:
            dispatch_began = perf_counter()
            first = dispatch_ready(plan, ledger, LocalHub(), router, worker_for=lambda _: "fixture-worker")
            initial_dispatch_seconds = perf_counter() - dispatch_began
        reopen_began = perf_counter()
        with Ledger(database) as reopened:
            snapshot = inspect_project(reopened, plan.project_id)
            inspect_seconds = perf_counter() - reopen_began
            resume_began = perf_counter()
            second = dispatch_ready(plan, reopened, LocalHub(), router, worker_for=lambda _: "fixture-worker")
            resume_seconds = perf_counter() - resume_began
            events = reopened.events(plan.project_id)
        total_seconds = perf_counter() - began

    expected_ids = tuple(part.id for part in plan.parts)
    require(first.started == expected_ids and not first.outcome_unknown and not first.not_ready,
            "first pass did not accept exactly the authored parts in order")
    require(not second.started and not second.outcome_unknown and not second.not_ready,
            "second pass was not empty")
    require(tuple(call[0] for call in calls) == expected_ids, "a part was omitted or replayed")
    require(all(part["state"] == "running" for part in snapshot["parts"]),
            "reopened ledger did not retain all accepted states")
    require(len(events) == 1 + 2 * count, "unexpected retained event count")
    for part in snapshot["parts"]:
        part.pop("updated_at")
    for event in events:
        event.pop("at")
    result = {
        "parts": count,
        "initial_dispatch_seconds": initial_dispatch_seconds,
        "reopen_inspect_seconds": inspect_seconds,
        "resume_seconds": resume_seconds,
        "total_seconds": total_seconds,
        "submitted": len(calls),
        "event_count": len(events),
        "semantic_sha256": stable_digest({"first": asdict(first), "second": asdict(second),
                                           "calls": calls, "snapshot": snapshot, "events": events}),
    }
    return result


def source_files(source):
    return {path.relative_to(source).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((source / "fanout_engine").glob("*.py"))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path)
    parser.add_argument("--after", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sizes", nargs="+", type=int, default=[500, 1500, 3000])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--receive-one", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--count", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.receive_one is not None:
        require(args.count is not None and args.count > 0, "a positive part count is required")
        print(json.dumps(receive_one(args.receive_one.resolve(), args.count)))
        return
    require(args.before is not None and args.after is not None and args.output is not None,
            "--before, --after and --output are required")
    require(args.repeats > 0 and all(count > 0 for count in args.sizes), "counts must be positive")
    require(not args.output.exists(), "output must be a new file")
    sources = {"before": args.before.resolve(), "after": args.after.resolve()}
    pins = {key: source_files(path) for key, path in sources.items()}
    require(all(pins.values()), "source checkout has no fanout_engine Python files")
    runs = []
    script = str(Path(__file__).resolve())
    for count in args.sizes:
        for repeat in range(args.repeats):
            # Alternate order so the candidate is not always the warm course.
            variants = ("before", "after") if repeat % 2 == 0 else ("after", "before")
            pair = {}
            for variant in variants:
                proc = subprocess.run([sys.executable, script, "--receive-one", str(sources[variant]),
                                       "--count", str(count)], capture_output=True, text=True,
                                      check=True, timeout=180)
                result = json.loads(proc.stdout)
                result.update({"variant": variant, "repeat": repeat + 1})
                runs.append(result)
                pair[variant] = result
                print(f"{variant}: parts={count} repeat={repeat + 1} "
                      f"total={result['total_seconds']:.6f}s resume={result['resume_seconds']:.6f}s",
                      flush=True)
            require(pair["before"]["semantic_sha256"] == pair["after"]["semantic_sha256"],
                    "before/after authored identities, calls, reports or retained events differ")
    require(pins == {key: source_files(path) for key, path in sources.items()},
            "source files changed during receiving")
    summary = []
    for count in args.sizes:
        row = {"parts": count}
        for variant in sources:
            sample = [run for run in runs if run["parts"] == count and run["variant"] == variant]
            row[variant] = {name: statistics.median(run[name] for run in sample) for name in (
                "initial_dispatch_seconds", "reopen_inspect_seconds", "resume_seconds", "total_seconds")}
        row["total_speedup"] = row["before"]["total_seconds"] / row["after"]["total_seconds"]
        row["resume_speedup"] = row["before"]["resume_seconds"] / row["after"]["resume_seconds"]
        summary.append(row)
    report = {"status": "passed", "python": platform.python_version(),
              "platform": platform.platform(), "sqlite": sqlite3.sqlite_version,
              "source_sha256": pins, "repeats": args.repeats,
              "summary": summary, "runs": runs,
              "limits": "Local fixture adapters and temporary SQLite only. Timings include native plan "
                        "construction, initial dispatch, close/reopen/inspection, no-replay resume and "
                        "event read; exclude fixture cleanup, result comparison and process startup. "
                        "No production worker or provider latency is measured."}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": report["status"], "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
