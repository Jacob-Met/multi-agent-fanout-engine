#!/usr/bin/env python3
"""Read the retained workflow through the maintained history CLI without mutation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _checkout import CHECKOUT, capture_source


def require(ok, detail):
    if not ok:
        raise SystemExit(detail)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--run", type=Path, required=True)
args = parser.parse_args()
source, run = CHECKOUT, args.run.resolve()
pin = json.loads((run / "source.json").read_text())
require(capture_source() == pin, "Checkout source changed since this run started")
receipt = json.loads((run / "receipt.json").read_text())
require(receipt["status"] == "completed" and receipt["source"] == pin, "Completed receiving/source binding mismatch")
db = run / "retained.sqlite3"
before = digest(db)
with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as connection:
    connection.row_factory = sqlite3.Row
    rows = connection.execute("SELECT * FROM events WHERE project_id=? ORDER BY seq", (receipt["project_id"],)).fetchall()
    all_events = [{**dict(row), "detail": json.loads(row["detail_json"])} for row in rows]
require(len(all_events) == 16, "Retained event count changed")
require(all_events == json.loads((run / "final-history.json").read_text()), "Saved history no longer matches SQLite")
output = run / "history-cli-receiving"
output.mkdir()
env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONOPTIMIZE"}}
env["PYTHONDONTWRITEBYTECODE"] = "1"
results = []
for label, part in [("whole-project", None), ("audit-part", "audit")]:
    command = [sys.executable, "-B", "-m", "fanout_engine.history", "--database", str(db), "--project", receipt["project_id"]]
    if part is not None:
        command += ["--part", part]
    result = subprocess.run(command, cwd=source, env=env, capture_output=True, timeout=15)
    (output / (label + ".stdout.json")).write_bytes(result.stdout)
    (output / (label + ".stderr.log")).write_bytes(result.stderr)
    require(result.returncode == 0, "Native history command failed")
    observed = json.loads(result.stdout)
    events = all_events if part is None else [event for event in all_events if event["part_id"] == part]
    expected = {"schema_version": 1, "project_id": receipt["project_id"], "plan_digest": receipt["plan_digest"],
                "part_id": part, "events": events}
    require(observed == expected, "Native history report differs from complete retained SQL evidence")
    require(digest(db) == before, "History CLI changed database bytes")
    require(capture_source() == pin, "Checkout source changed during history receiving")
    results.append({"label": label, "command": command, "cwd": str(source), "returncode": 0,
                    "event_count": len(events), "all_selected_persisted_events_returned": True,
                    "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                    "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()})
require([event["event"] for event in all_events if event["part_id"] == "audit"]
        == ["dispatch_started", "outcome_unknown", "reconciled"], "Audit timeline lost its unknown evidence")
receiving = {"decision": "accepted", "source_manifest_sha256": pin["manifest_sha256"],
             "history_blob": next(item["blob"] for item in pin["files"] if item["path"] == "fanout_engine/history.py"),
             "results": results, "database_sha256_before": before, "database_sha256_after": digest(db),
             "database_bytes_unchanged": True, "provider_calls": 0, "dispatch_calls": 0,
             "qualification": "Two actual read-only native CLI processes against the completed authored local workflow. Reports match all persisted SQLite rows, including exact JSON text, ordered sequence, unknown evidence and reconciliation."}
(output / "receipt.json").write_text(json.dumps(receiving, indent=2) + "\n")
print(json.dumps(receiving, indent=2))
