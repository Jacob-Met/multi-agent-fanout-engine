"""Whole local plan/ledger/inspection timings, using identical authored inputs."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("--sizes", default="256,1024,4096")
parser.add_argument("--repeats", type=int, default=3)
args = parser.parse_args()
sys.path.insert(0, str(args.source.resolve()))
from fanout_engine import Ledger, Plan, inspect_project

rows = []
for count in map(int, args.sizes.split(",")):
    raw = {"project": "key-cost", "parts": [
        {"id": f"p{i}", "instruction": f"Local fixture {i}",
         "depends_on": [f"p{i-1}"] if i else [], "tags": []}
        for i in range(count)
    ]}
    samples = []
    hashes = set()
    for repeat in range(args.repeats):
        start = time.perf_counter()
        plan = Plan.from_dict(raw)
        planned = time.perf_counter()
        with Ledger(":memory:") as ledger:
            ledger.record_plan(plan)
            recorded = time.perf_counter()
            report = inspect_project(ledger, plan.project_id)
            inspected = time.perf_counter()
        for part in report["parts"]:
            del part["updated_at"]
        digest = hashlib.sha256(json.dumps(report, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        hashes.add(digest)
        samples.append({"plan_s": planned-start, "record_s": recorded-planned,
                        "inspect_s": inspected-recorded, "total_s": inspected-start})
    if len(hashes) != 1:
        raise AssertionError("normalized whole reports differ between identical runs")
    rows.append({"parts": count, "samples": samples,
                 "median_s": {k: statistics.median(s[k] for s in samples) for k in samples[0]},
                 "normalized_report_sha256": next(iter(hashes))})
print(json.dumps({"source": str(args.source), "python": sys.version, "rows": rows}, indent=2))
