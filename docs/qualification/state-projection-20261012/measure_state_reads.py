"""Paired disk-ledger receiving with synthetic retained evidence and no provider.

Run this file with --before SOURCE --after SOURCE. Both sources receive the
same native SQLite fixture in fresh processes, in alternating order.
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
import tempfile
import time
import tracemalloc


def document(parts):
    return {"project": "state-read-receiving", "parts": [
        {"id": f"p{i:04d}", "instruction": "Local work."} for i in range(parts)
    ]}


def digest_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def imports(source):
    sys.path.insert(0, str(Path(source).resolve()))
    from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project
    from fanout_engine.plan import canonical_json
    return EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project, canonical_json


def child(args):
    EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project, canonical_json = imports(args.source)
    router = EffortRouter({"local-model": ("low",)}, pool=(Route("local-model", "low"),))

    class LocalHub:
        def __init__(self):
            self.calls = []

        def submit(self, part, **kwargs):
            self.calls.append((part.id, kwargs["idempotency_key"]))
            return {"task_id": "task-" + part.id}

    if args.mode == "fixture":
        start = time.perf_counter()
        plan = Plan.from_dict(document(args.parts))
        evidence = {"source": "synthetic receiving", "locator": "fixture:local",
                    "finding": "x" * max(1, args.finding_bytes)}
        hub = LocalHub()
        with Ledger(args.database) as ledger:
            report = dispatch_ready(plan, ledger, hub, router, worker_for=lambda part: "local-worker")
            assert report.started == tuple(part.id for part in plan.parts)
            assert hub.calls == [(part.id, plan.idempotency_key(part.id)) for part in plan.parts]
            for index, part in enumerate(plan.parts):
                if index % 2:
                    ledger.mark_outcome_unknown(plan.project_id, part.id, evidence)
                else:
                    ledger.mark_completed(plan.project_id, part.id, "artifact:" + part.id, evidence)
        return {"fixture_create_s": time.perf_counter() - start,
                "database_bytes": Path(args.database).stat().st_size,
                "database_sha256": digest_file(args.database)}

    before_sha = digest_file(args.database)
    start = time.perf_counter()
    plan = Plan.from_dict(document(args.parts))
    hub = LocalHub()
    dispatch_seconds, reports = [], []
    with Ledger(args.database) as ledger:
        open_plan_s = time.perf_counter() - start
        for _ in range(args.passes):
            step = time.perf_counter()
            report = dispatch_ready(plan, ledger, hub, router, worker_for=lambda part: "local-worker")
            dispatch_seconds.append(time.perf_counter() - step)
            assert report.started == report.outcome_unknown == report.not_ready == ()
            reports.append(asdict(report))
        dispatch_workflow_s = time.perf_counter() - start
        step = time.perf_counter()
        report = inspect_project(ledger, plan.project_id)
        encoded = canonical_json(report).encode("utf-8")
        inspection_and_serialization_s = time.perf_counter() - step
        assert report["state_counts"]["completed"] == (args.parts + 1) // 2
        assert report["state_counts"]["outcome_unknown"] == args.parts // 2
        assert report["queued_ready_ids"] == []
        assert not hub.calls
    complete_workflow_s = time.perf_counter() - start

    # Separate diagnostics do not instrument the wall-time samples above.
    expected_states = tuple("outcome_unknown" if i % 2 else "completed" for i in range(args.parts))
    with Ledger.open_readonly(args.database) as ledger:
        tracemalloc.start()
        states = tuple(ledger.part_state(plan.project_id, part.id) for part in plan.parts)
        _, state_peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert states == expected_states
        transferred = {"rows": 0, "text_utf8_bytes": 0}

        def count_row(cursor, row):
            transferred["rows"] += 1
            transferred["text_utf8_bytes"] += sum(len(value.encode("utf-8"))
                                                    for value in row if isinstance(value, str))
            return sqlite3.Row(cursor, row)

        ledger._db.row_factory = count_row
        assert tuple(ledger.part_state(plan.project_id, part.id) for part in plan.parts) == expected_states
    assert digest_file(args.database) == before_sha
    source_bytes = (Path(args.source) / "fanout_engine/ledger.py").read_bytes()
    return {"ledger_sha256": hashlib.sha256(source_bytes).hexdigest(),
            "open_plan_s": open_plan_s, "dispatch_s": dispatch_seconds,
            "dispatch_workflow_s": dispatch_workflow_s,
            "inspection_and_serialization_s": inspection_and_serialization_s,
            "complete_workflow_s": complete_workflow_s,
            "state_peak_python_bytes": state_peak_bytes, "state_row_transfer": transferred,
            "report_sha256": hashlib.sha256(encoded).hexdigest(), "report_bytes": len(encoded),
            "database_sha256": before_sha, "database_unchanged": True, "hub_calls": len(hub.calls),
            "dispatch_reports": reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before")
    parser.add_argument("--after")
    parser.add_argument("--parts", type=int, default=128)
    parser.add_argument("--finding-bytes", type=int, nargs="+", default=[1, 65536, 262144])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--passes", type=int, default=3)
    parser.add_argument("--mode", choices=("fixture", "receive"))
    parser.add_argument("--source")
    parser.add_argument("--database")
    args = parser.parse_args()
    if args.mode:
        args.finding_bytes = args.finding_bytes[0]
        print(json.dumps(child(args), sort_keys=True))
        return
    if not args.before or not args.after or min(args.parts, args.repeats, args.passes) < 1:
        parser.error("before/after sources and positive parts/repeats/passes are required")

    def run(mode, source, database, finding_bytes):
        command = [sys.executable, str(Path(__file__).resolve()), "--mode", mode,
                   "--source", str(Path(source).resolve()), "--database", str(database),
                   "--parts", str(args.parts), "--passes", str(args.passes),
                   "--finding-bytes", str(finding_bytes)]
        result = subprocess.run(command, text=True, capture_output=True, check=True)
        return json.loads(result.stdout)

    result = {"python": sys.version, "platform": platform.platform(), "sqlite": sqlite3.sqlite_version,
              "parts": args.parts, "passes": args.passes, "repeats": args.repeats,
              "method": "same native disk fixture; fresh processes; alternating before/after order; no provider",
              "cases": []}
    for finding_bytes in args.finding_bytes:
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "ledger.sqlite"
            fixture = run("fixture", args.before, database, finding_bytes)
            samples = {"before": [], "after": []}
            for repetition in range(args.repeats):
                order = ("before", "after") if repetition % 2 == 0 else ("after", "before")
                for label in order:
                    samples[label].append(run("receive", getattr(args, label), database, finding_bytes))
            flattened = samples["before"] + samples["after"]
            assert len({sample["report_sha256"] for sample in flattened}) == 1
            assert all(sample["database_sha256"] == fixture["database_sha256"] for sample in flattened)
            medians = {label: {
                "first_dispatch_s": statistics.median(s["dispatch_s"][0] for s in items),
                "dispatch_workflow_s": statistics.median(s["dispatch_workflow_s"] for s in items),
                "inspection_and_serialization_s": statistics.median(s["inspection_and_serialization_s"] for s in items),
                "complete_workflow_s": statistics.median(s["complete_workflow_s"] for s in items),
                "state_peak_python_bytes": statistics.median(s["state_peak_python_bytes"] for s in items),
            } for label, items in samples.items()}
            result["cases"].append({"finding_bytes": finding_bytes, "fixture": fixture,
                                    "medians": medians, "samples": samples})
            print(f"received {args.parts} parts / {finding_bytes} finding bytes", file=sys.stderr, flush=True)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
