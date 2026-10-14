#!/usr/bin/env python3
"""Frozen independent public-command receiver for retained-handoff route adoption."""
from __future__ import annotations
import argparse
from contextlib import closing
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import stat
import subprocess
import sys
import traceback

def sha(data):
    return hashlib.sha256(data).hexdigest()

def read(path):
    return json.loads(path.read_bytes())

def observed(path):
    data = path.read_bytes()
    info = path.stat()
    return {"bytes": len(data), "sha256": sha(data), "mode": stat.S_IMODE(info.st_mode),
            "mtime_ns": info.st_mtime_ns}

def fence(root):
    return {p.relative_to(root).as_posix(): observed(p) for p in sorted(root.rglob("*")) if p.is_file()}

def emit(path, value):
    with path.open("xb") as stream:
        stream.write((json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

def group_absent(pid):
    try:
        os.killpg(pid, 0)
        return False
    except ProcessLookupError:
        return True

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("mode", choices=("original", "candidate"))
parser.add_argument("--original-output", type=Path)
args = parser.parse_args()
source = args.source.resolve()
out = args.output.absolute()
if args.mode == "candidate" and args.original_output is None:
    parser.error("candidate needs --original-output from the completed original course")
original = args.original_output.resolve() if args.original_output else None
expect_path = Path(__file__).resolve().with_name("retained-route-expectations-v1.json")
expected = read(expect_path)
out.mkdir()
cwd = out / "unrelated-cwd"
cwd.mkdir()
run = out / "retained workflow 雪"
checks = []
children = []
receipt = {"schema_version": 1, "mode": args.mode, "started_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "source": str(source), "output": str(out), "python": sys.version, "executable": sys.executable,
           "expectations": expected, "checks": checks, "children": children, "error": None}
before = fence(source)
oracle_before = {str(p): observed(p) for p in (Path(__file__).resolve(), expect_path)}
original_before = fence(original) if original else None
env = {k: v for k, v in os.environ.items() if k not in
       {"PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONOPTIMIZE"}}
env["PYTHONDONTWRITEBYTECODE"] = "1"

def check(name, ok, detail=None):
    checks.append({"name": name, "passed": bool(ok), "detail": detail})

def child(label, command, timeout=120):
    proc = subprocess.Popen(command, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    row = {"label": label, "command": command, "cwd": str(cwd), "pid": proc.pid, "signals": []}
    children.append(row)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        row["timed_out"] = True
        row["signals"].append("SIGTERM")
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            stdout, stderr = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            row["signals"].append("SIGKILL")
            os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate(timeout=2)
    with (out / (label + ".stdout")).open("xb") as stream:
        stream.write(stdout)
    with (out / (label + ".stderr")).open("xb") as stream:
        stream.write(stderr)
    row.update(returncode=proc.returncode, stdout_sha256=sha(stdout), stderr_sha256=sha(stderr),
               stdout_bytes=len(stdout), stderr_bytes=len(stderr), group_absent=group_absent(proc.pid))
    return row, stdout, stderr

try:
    example = source / "examples/retained_handoff"
    fixture = example / "fixtures"
    plan = read(fixture / "plan.json")
    part_ids = [p["id"] for p in plan["parts"]]
    dependencies = {p["id"]: p.get("depends_on", []) for p in plan["parts"]}
    command = [sys.executable, "-I", "-B", str(example / "run_consumer.py"), "--output", str(run)]
    row, stdout, stderr = child("public-consumer", command)
    check("public consumer completes with empty stderr", row["returncode"] == 0 and not stderr)
    if row["returncode"] != 0:
        raise RuntimeError("public consumer did not finish; retained raw outputs identify the boundary")
    summary = read(run / "receipt.json")
    check("stdout is the saved final receipt", json.loads(stdout) == summary)
    check("five-part local workflow is unchanged",
          all(summary.get(k) == v for k, v in expected["workflow"].items())
          and summary["status"] == "completed" and summary["scope"] == "authored-local-fixture"
          and summary["project_id"] == plan["project"])
    pin = read(run / "source.json")
    projected = []
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source).as_posix()
        if path.is_file() and ((rel.startswith("fanout_engine/") and path.suffix == ".py")
                or (path.parent == example and path.suffix == ".py")
                or rel.startswith("examples/retained_handoff/fixtures/")):
            data = path.read_bytes()
            projected.append({"path": rel, "bytes": len(data), "sha256": sha(data),
                              "blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()})
    projected.sort(key=lambda r: r["path"])
    compact = json.dumps(projected, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    check("full observed source projection is exact",
          pin == {"schema_version": 1, "kind": "observed-checkout-files", "files": projected,
                  "manifest_sha256": sha(compact)} and summary["source"] == pin)
    phases = [read(run / (p["phase"] + "-receipt.json")) for p in expected["phases"]]
    check("four fresh phases remain in order",
          [p["phase"] for p in phases] == [p["phase"] for p in expected["phases"]]
          and len({p["pid"] for p in phases}) == 4
          and all(p["pid"] != row["pid"] for p in phases)
          and [p["phase"] for p in summary["processes"]] == [p["phase"] for p in expected["phases"]])
    for phase, exp, meta in zip(phases, expected["phases"], summary["processes"]):
        label = exp["label"]
        state = read(run / (label + "-state.json"))
        history = read(run / (label + "-history.json"))
        inspect_bytes = (run / (label + "-inspect.stdout.json")).read_bytes()
        counts = {key: 0 for key in ("completed", "dispatching", "failed", "outcome_unknown", "queued", "running")}
        for value in exp["states"].values():
            counts[value] += 1
        check(label + " retained state and history",
              state["project_id"] == plan["project"] and state["plan_digest"] == summary["plan_digest"]
              and state["state_counts"] == counts and state["queued_ready_ids"] == exp["ready"]
              and state["blocked_queued_ids"] == exp["blocked"]
              and [p["id"] for p in state["parts"]] == part_ids
              and {p["id"]: p["state"] for p in state["parts"]} == exp["states"]
              and len(history) == exp["events"] == phase["event_count"]
              and json.loads(inspect_bytes) == state)
        check(label + " phase streams and original read fence",
              meta["returncode"] == 0 and meta["stdout_sha256"] == sha((run / (exp["phase"] + ".stdout.json")).read_bytes())
              and meta["stderr_sha256"] == sha(b"") and (run / (exp["phase"] + ".stderr.log")).read_bytes() == b""
              and phase["database_bytes_unchanged_by_readers"] is True
              and phase["all_persisted_events_read"] is True
              and phase["source_manifest_sha256"] == pin["manifest_sha256"])
        filename = label + "-queued-routes.stdout.json"
        path = run / filename
        if args.mode == "original":
            check(label + " records capability absence", not path.exists()
                  and not (run / (label + "-queued-routes.stderr.log")).exists()
                  and all(k not in phase for k in expected["phase_additions"]))
        else:
            report_bytes = path.read_bytes()
            report = json.loads(report_bytes)
            keys = {p["id"]: "fanout-" + sha((plan["project"] + "\0" + summary["plan_digest"] + "\0" + p["id"]).encode())
                    for p in state["parts"]}
            routes = [{**expected["route"], "idempotency_key": keys["summary"]}] if exp["ready"] else []
            parts = [{"id": p["id"], "state": exp["states"][p["id"]],
                      "unmet_dependencies": [{"id": d, "state": exp["states"][d]}
                                             for d in dependencies[p["id"]] if exp["states"][d] != "completed"]}
                     for p in state["parts"]]
            target = {"schema_version": 1, "project_id": plan["project"], "plan_digest": summary["plan_digest"],
                      "state_counts": counts, "queued_ready_ids": exp["ready"], "blocked_queued_ids": exp["blocked"],
                      "parts": parts, "routes": routes, "configured_step_up": None,
                      "routing_input_sha256": sha((fixture / "routes.json").read_bytes())}
            check(label + " exact queued-route report", report == target
                  and all(p["idempotency_key"] == keys[p["id"]] for p in state["parts"]),
                  {"expected": target, "actual": report})
            check(label + " canonical route bytes",
                  report_bytes == (json.dumps(target, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode())
            command_meta = phase["queued_route_command"]
            route_args = ["-B", "-m", "fanout_engine.queued_routes", "--database", str(run / "retained.sqlite3"),
                          "--project", plan["project"], "--routes", str(fixture / "routes.json")]
            check(label + " actual CLI command and artifact binding",
                  command_meta["command"] == [sys.executable, *route_args] and command_meta["cwd"] == str(source)
                  and command_meta["returncode"] == 0 and command_meta["stdout_sha256"] == sha(report_bytes)
                  and command_meta["stderr_sha256"] == sha(b"")
                  and (run / (label + "-queued-routes.stderr.log")).read_bytes() == b""
                  and phase["queued_route_report"] == filename and phase["queued_route_ready_ids"] == exp["ready"])
    report_names = [p["label"] + "-queued-routes.stdout.json" for p in expected["phases"]]
    check("final route report index", expected["final_addition"] not in summary if args.mode == "original"
          else summary["queued_route_reports"] == report_names)
    calls_bytes = (run / "adapter-calls.jsonl").read_bytes()
    calls = [json.loads(line) for line in calls_bytes.splitlines()]
    check("five unique adapter calls and no audit replay",
          [r["part_id"] for r in calls] == part_ids and len({r["idempotency_key"] for r in calls}) == 5)
    preview_bytes = (run / "preview.stdout.json").read_bytes()
    preview = json.loads(preview_bytes)
    check("authored plan preview still shows all routes", [p["part_id"] for p in preview["routes"]] == part_ids
          and [p["route"]["effort"] for p in preview["routes"]] == ["ultra", "low", "low", "low", "low"])
    db = run / "retained.sqlite3"
    db_before = observed(db)
    with closing(sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        rows = [dict(r) for r in connection.execute("SELECT * FROM events WHERE project_id=? ORDER BY seq", (plan["project"],))]
        part_rows = [dict(r) for r in connection.execute("SELECT part_id,state,idempotency_key FROM parts WHERE project_id=?", (plan["project"],))]
    events = [{**r, "detail": json.loads(r["detail_json"])} for r in rows]
    check("raw final SQLite agrees with retained history",
          events == read(run / "final-history.json") and len(events) == 16
          and {r["part_id"]: r["state"] for r in part_rows} == expected["phases"][-1]["states"]
          and [e["event"] for e in events if e["part_id"] == "audit"] == ["dispatch_started", "outcome_unknown", "reconciled"]
          and observed(db) == db_before)
    check("hold preserves history", (run / "unknown-history.json").read_bytes() == (run / "held-history.json").read_bytes())
    prior_files = fence(run)
    hrow, hout, herr = child("public-history", [sys.executable, "-I", "-B", str(example / "receive_history_cli.py"), "--run", str(run)], timeout=60)
    check("documented history receiver stays usable",
          hrow["returncode"] == 0 and not herr and read(run / "history-cli-receiving/receipt.json")["decision"] == "accepted")
    check("history receiving preserves DB and every earlier run file",
          observed(db) == db_before and all(observed(run / p) == v for p, v in prior_files.items()))
    complete = fence(run)
    rrow, rout, rerr = child("occupied-output", command, timeout=30)
    check("occupied output is refused without retained mutation",
          rrow["returncode"] != 0 and bool(rerr) and fence(run) == complete)
    if original:
        prior_run = original / run.name
        check("all five artifact bytes preserve original control",
              {p.name: p.read_bytes() for p in (run / "artifacts").iterdir()}
              == {p.name: p.read_bytes() for p in (prior_run / "artifacts").iterdir()})
        check("adapter calls and authored preview preserve original bytes",
              calls_bytes == (prior_run / "adapter-calls.jsonl").read_bytes()
              and preview_bytes == (prior_run / "preview.stdout.json").read_bytes())
    receipt["run_files"] = fence(run)
except Exception as exc:
    receipt["error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
finally:
    after = fence(source)
    check("source bytes modes and mtimes unchanged", after == before)
    check("frozen helper and expectations unchanged", oracle_before == {str(p): observed(p) for p in (Path(__file__).resolve(), expect_path)})
    if original:
        check("original receiving control remains unchanged", fence(original) == original_before)
    check("all owned child process groups absent without forced signal",
          bool(children) and all(c.get("group_absent") and not c["signals"] and not c.get("timed_out") for c in children))
    receipt.update(source_before=before, source_after=after, oracle_before=oracle_before,
                   finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   passed=sum(c["passed"] for c in checks), failed=sum(not c["passed"] for c in checks))
    emit(out / "RECEIVING.json", receipt)
    print(json.dumps({"receipt": str(out / "RECEIVING.json"), "passed": receipt["passed"],
                      "failed": receipt["failed"], "error": receipt["error"],
                      "sha256": sha((out / "RECEIVING.json").read_bytes())}, ensure_ascii=False))
sys.exit(2 if receipt["error"] else 1 if receipt["failed"] else 0)
