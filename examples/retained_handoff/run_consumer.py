#!/usr/bin/env python3
"""Produce a local fixture handoff through the native durable fanout workflow."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures"
sys.path.insert(0, str(ROOT))
from _checkout import CHECKOUT, capture_source


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save_new(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    with path.open("xb") as stream:
        stream.write(data)
    return sha(data)


def bytes_new(path, data):
    with path.open("xb") as stream:
        stream.write(data)


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, required=True, help="new retained run directory")
parser.add_argument("--phase", choices=("all", "start", "resume", "hold", "reconcile"), default="all", help=argparse.SUPPRESS)
args = parser.parse_args()
SOURCE, OUTPUT = CHECKOUT, args.output.absolute()
source_pin = capture_source()
if args.phase != "all":
    require(source_pin == load(OUTPUT / "source.json"), "Checkout source changed since this run started")
for item in load(FIXTURE / "fixture-pin.json")["files"]:
    require(sha((FIXTURE / item["path"]).read_bytes()) == item["sha256"], "Authored fixture changed: " + item["path"])

sys.path.insert(0, str(SOURCE))
from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project

plan = Plan.from_dict(load(FIXTURE / "plan.json"))
config = load(FIXTURE / "routes.json")
router = EffortRouter(config["catalog"], pool=[Route(**row) for row in config["pool"]])
overrides = {key: Route(**value) for key, value in config["explicit_routes"].items()}
DB = OUTPUT / "retained.sqlite3"
env = {key: value for key, value in os.environ.items()
       if key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE", "PYTHONSTARTUP"}}
env["PYTHONDONTWRITEBYTECODE"] = "1"


def native_cli(label, arguments):
    require(capture_source() == source_pin, "Checkout source changed before native CLI")
    command = [sys.executable, "-B", "-m", *arguments]
    result = subprocess.run(command, cwd=SOURCE, env=env, capture_output=True, timeout=15)
    bytes_new(OUTPUT / (label + ".stdout.json"), result.stdout)
    bytes_new(OUTPUT / (label + ".stderr.log"), result.stderr)
    require(result.returncode == 0, label + " failed: " + result.stderr.decode(errors="replace"))
    require(capture_source() == source_pin, "Checkout source changed during native CLI")
    return json.loads(result.stdout), {"command": command, "cwd": str(SOURCE), "returncode": result.returncode,
                                     "stdout_sha256": sha(result.stdout), "stderr_sha256": sha(result.stderr)}


def journal_path(part_id):
    return OUTPUT / "adapter-journal" / (plan.idempotency_key(part_id) + ".json")


def artifact_ref(journal):
    return journal["artifact"] + "#sha256=" + journal["artifact_sha256"]


def validate_journal(part_id):
    journal = load(journal_path(part_id))
    require(journal["scope"] == "authored-local-fixture" and journal["status"] == "completed", "Unexpected journal scope/status")
    require(journal["project_id"] == plan.project_id and journal["part_id"] == part_id,
            "Journal project/part mismatch")
    require(journal["idempotency_key"] == plan.idempotency_key(part_id), "Journal stable key mismatch")
    require(journal["plan_digest"] == plan.digest, "Journal plan digest mismatch")
    actual = (OUTPUT / journal["artifact"]).read_bytes()
    require(sha(actual) == journal["artifact_sha256"], "Journal artifact digest mismatch")
    return journal


class UnreadableAcknowledgement(dict):
    def get(self, *_args, **_kwargs):
        raise OSError("Authored fixture acknowledgement is unreadable after local completion")


class LocalFileAdapter:
    """Only local deterministic file work; route labels are retained metadata."""

    def submit(self, part, *, route, worker_id, idempotency_key):
        require(idempotency_key == plan.idempotency_key(part.id), "Submission stable key mismatch")
        require(not journal_path(part.id).exists(), "Duplicate local submission refused: " + part.id)
        declared = load(FIXTURE / "expected-files.json")["files"]
        actual = [{"path": row["path"], "bytes": len((FIXTURE / row["path"]).read_bytes()),
                   "sha256": sha((FIXTURE / row["path"]).read_bytes())} for row in declared]
        if part.id == "audit":
            require(actual == declared, "Fixture integrity audit failed")
            result = {"scope": "authored-local-fixture", "verified": True, "files": actual}
        elif part.id == "inventory":
            result = {"files": actual, "file_count": len(actual), "total_bytes": sum(row["bytes"] for row in actual)}
        elif part.id == "notes":
            result = {"receiving_notes": [
                "Read the recorded routes and plan digest before dispatch.",
                "An unreadable acknowledgement remains unknown across process restarts.",
                "Use the exact stable-key journal and artifact digest before reconciliation.",
                "Read all retained events after the current-state report.",
            ], "provider_calls": 0, "input_scope": "Three authored local files"}
        elif part.id == "summary":
            inventory = load(OUTPUT / "artifacts/inventory.json")
            result = {"purpose": "Portable fixture receiving handoff", "file_count": inventory["file_count"],
                      "total_bytes": inventory["total_bytes"], "input_manifest_sha256": sha((FIXTURE / "expected-files.json").read_bytes())}
        elif part.id == "handoff":
            dependencies = {part_id: validate_journal(part_id) for part_id in ("audit", "inventory", "notes", "summary")}
            result = {"project_id": plan.project_id, "plan_digest": plan.digest, "scope": "authored-local-fixture",
                      "artifacts": [{"part_id": part_id, "ref": artifact_ref(journal)} for part_id, journal in dependencies.items()],
                      "summary": load(OUTPUT / "artifacts/summary.json"),
                      "receiving_notes": load(OUTPUT / "artifacts/notes.json")["receiving_notes"]}
        else:
            raise RuntimeError("Unknown authored part")
        target = OUTPUT / "artifacts" / (part.id + ".json")
        artifact_hash = save_new(target, result)
        journal = {"scope": "authored-local-fixture", "status": "completed", "project_id": plan.project_id,
                   "plan_digest": plan.digest, "part_id": part.id, "idempotency_key": idempotency_key,
                   "task_id": "fixture-task-" + part.id, "worker_id": worker_id, "route": asdict(route),
                   "artifact": target.relative_to(OUTPUT).as_posix(), "artifact_sha256": artifact_hash}
        save_new(journal_path(part.id), journal)
        with (OUTPUT / "adapter-calls.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"part_id": part.id, "idempotency_key": idempotency_key,
                                     "route": asdict(route), "worker_id": worker_id}) + "\n")
        return UnreadableAcknowledgement() if part.id == "audit" else {"task_id": journal["task_id"]}


def call_log():
    path = OUTPUT / "adapter-calls.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def dispatch_and_finish(ledger):
    report = dispatch_ready(plan, ledger, LocalFileAdapter(), router,
                            worker_for=lambda part: "local-file-worker-" + part.id,
                            explicit_routes=overrides)
    for part_id in report.started:
        journal = validate_journal(part_id)
        ledger.mark_completed(plan.project_id, part_id, artifact_ref(journal), evidence={
            "source": "authored local file adapter",
            "locator": journal_path(part_id).relative_to(OUTPUT).as_posix(),
            "finding": "Completed local artifact digest matches the exact stable-key journal.",
        })
    return asdict(report)


def capture(label):
    before = sha(DB.read_bytes())
    with Ledger.open_readonly(DB) as ledger:
        state = inspect_project(ledger, plan.project_id)
        history = ledger.events(plan.project_id)
        audit_history = ledger.events(plan.project_id, "audit")
    with sqlite3.connect(DB.as_uri() + "?mode=ro", uri=True) as sql:
        rows = sql.execute("SELECT seq,part_id,event,detail_json FROM events WHERE project_id=? ORDER BY seq", (plan.project_id,)).fetchall()
    require([(event["seq"], event["part_id"], event["event"], event["detail_json"]) for event in history] == rows,
            "History API did not return every persisted event exactly")
    require(audit_history == [event for event in history if event["part_id"] == "audit"], "Part history filter mismatch")
    native, command = native_cli(label + "-inspect", ["fanout_engine.inspect", "--database", str(DB), "--project", plan.project_id])
    require(native == state, "Native inspection CLI/API disagree")
    queued, queued_command = native_cli(label + "-queued-routes", [
        "fanout_engine.queued_routes", "--database", str(DB), "--project", plan.project_id,
        "--routes", str(FIXTURE / "routes.json")])
    require(queued["schema_version"] == 1, "Unexpected queued-route report schema")
    for key in ("project_id", "plan_digest", "state_counts", "queued_ready_ids", "blocked_queued_ids"):
        require(queued[key] == state[key], "Queued-route inspection mismatch: " + key)
    require(queued["routing_input_sha256"] == sha((FIXTURE / "routes.json").read_bytes()),
            "Queued-route input digest mismatch")
    require(queued["parts"] == [
        {"id": part["id"], "state": part["state"], "unmet_dependencies": part["unmet_dependencies"]}
        for part in state["parts"]], "Queued-route retained state context mismatch")
    stored = {part["id"]: part for part in state["parts"]}
    expected_routes = [
        {"part_id": part_id, "route": asdict(router.route_for(part_id, overrides.get(part_id))),
         "route_source": "explicit" if part_id in overrides else "pool",
         "idempotency_key": stored[part_id]["idempotency_key"]}
        for part_id in state["queued_ready_ids"]]
    require(queued["routes"] == expected_routes, "Queued-route selection or stored key mismatch")
    require(queued["configured_step_up"] is None, "Unexpected fixture step-up route")
    blockers, blocker_command = native_cli(label + "-blockers", [
        "fanout_engine.blockers", "--database", str(DB), "--project", plan.project_id])
    require(label in ("initial", "unknown", "held", "final"), "Unknown retained capture")
    frontier_ids = ["audit", "summary"] if label == "initial" else (
        [] if label == "final" else ["audit"])
    expected_blockers = {
        "schema_version": 1, "project_id": plan.project_id, "plan_digest": plan.digest,
        "queued_ready_ids": state["queued_ready_ids"],
        "blocked_queued": [] if label == "final" else [{
            "id": "handoff", "direct_unmet_ids": frontier_ids, "frontier_ids": frontier_ids}],
        "frontier": [{"id": part_id, "state": stored[part_id]["state"],
                      "worker_id": stored[part_id]["worker_id"],
                      "task_id": stored[part_id]["task_id"], "blocked_queued_ids": ["handoff"]}
                     for part_id in frontier_ids],
    }
    require(blockers == expected_blockers, "Blocker report differs from the retained fixture phase")
    require(sha(DB.read_bytes()) == before, "Read-only receiving changed database bytes")
    save_new(OUTPUT / (label + "-state.json"), state)
    save_new(OUTPUT / (label + "-history.json"), history)
    save_new(OUTPUT / (label + "-audit-history.json"), audit_history)
    return state, history, {"event_count": len(history), "database_sha256": before,
                            "all_persisted_events_read": True, "database_bytes_unchanged_by_readers": True,
                            "inspection_command": command, "queued_route_command": queued_command,
                            "queued_route_report": label + "-queued-routes.stdout.json",
                            "queued_route_ready_ids": queued["queued_ready_ids"],
                            "blocker_command": blocker_command,
                            "blocker_report": label + "-blockers.stdout.json",
                            "blocker_frontier_ids": frontier_ids}


def stage_start():
    DB.touch(exist_ok=False)
    (OUTPUT / "artifacts").mkdir()
    (OUTPUT / "adapter-journal").mkdir()
    preview, command = native_cli("preview", ["fanout_engine.preview", "--plan", str(FIXTURE / "plan.json"),
                                               "--routes", str(FIXTURE / "routes.json")])
    require(preview["plan_digest"] == plan.digest, "Preview plan digest mismatch")
    require([(row["part_id"], row["route"]["effort"]) for row in preview["routes"]]
            == [(part.id, "ultra" if part.id == "audit" else "low") for part in plan.parts], "Preview route mismatch")
    with Ledger(str(DB)) as ledger:
        dispatch = dispatch_and_finish(ledger)
    require(dispatch == {"started": ("inventory", "notes"), "outcome_unknown": ("audit",), "not_ready": ("summary", "handoff")},
            "Initial independent continuation mismatch")
    state, history, receiving = capture("initial")
    require(state["state_counts"]["completed"] == 2 and state["state_counts"]["outcome_unknown"] == 1, "Initial retained states mismatch")
    require(state["queued_ready_ids"] == ["summary"] and state["blocked_queued_ids"] == ["handoff"], "Initial dependency state mismatch")
    return {"dispatch": dispatch, "preview_command": command, **receiving}


def stage_resume():
    before = call_log()
    with Ledger(str(DB)) as ledger:
        require(ledger.part_state(plan.project_id, "audit") == "outcome_unknown", "Unknown did not survive reopen")
        dispatch = dispatch_and_finish(ledger)
    require(dispatch == {"started": ("summary",), "outcome_unknown": (), "not_ready": ("handoff",)}, "Resume dispatch mismatch")
    require([row["part_id"] for row in call_log()[len(before):]] == ["summary"], "Reopen replayed prior work")
    state, history, receiving = capture("unknown")
    require(state["state_counts"]["completed"] == 3 and state["state_counts"]["outcome_unknown"] == 1
            and state["blocked_queued_ids"] == ["handoff"], "Unknown phase mismatch")
    require([event["event"] for event in history if event["part_id"] == "audit"]
            == ["dispatch_started", "outcome_unknown"], "Unknown evidence timeline mismatch")
    return {"dispatch": dispatch, "prior_work_replayed": False, **receiving}


def stage_hold():
    before_calls = (OUTPUT / "adapter-calls.jsonl").read_bytes()
    with Ledger(str(DB)) as ledger:
        before_events = ledger.events(plan.project_id)
        dispatch = dispatch_and_finish(ledger)
        require(ledger.events(plan.project_id) == before_events, "Idle hold added ledger events")
    require(dispatch == {"started": (), "outcome_unknown": (), "not_ready": ("handoff",)}, "Hold dispatch mismatch")
    require((OUTPUT / "adapter-calls.jsonl").read_bytes() == before_calls, "Unknown or completed work was replayed")
    state, history, receiving = capture("held")
    return {"dispatch": dispatch, "new_adapter_calls": 0, "retained_history_unchanged": True, **receiving}


def stage_reconcile():
    journal = validate_journal("audit")
    require(journal["route"] == {"model": "fixture-local", "effort": "ultra"}, "Retained ultra route changed")
    journal_digest = sha(journal_path("audit").read_bytes())
    evidence = {"source": "authored local adapter completion journal",
                "locator": journal_path("audit").relative_to(OUTPUT).as_posix() + "#sha256=" + journal_digest,
                "finding": "Exact project, part, stable key and plan digest identify one completed local integrity audit; artifact bytes match its recorded digest."}
    before = call_log()
    with Ledger(str(DB)) as ledger:
        ledger.reconcile_unknown(plan.project_id, "audit", verdict="completed", evidence=evidence, artifact_ref=artifact_ref(journal))
        dispatch = dispatch_and_finish(ledger)
    require(dispatch == {"started": ("handoff",), "outcome_unknown": (), "not_ready": ()}, "Reconciled handoff did not complete")
    require([row["part_id"] for row in call_log()[len(before):]] == ["handoff"], "Reconciliation replayed audit")
    state, history, receiving = capture("final")
    require(state["state_counts"]["completed"] == 5, "Final workflow is incomplete")
    require([event["event"] for event in history if event["part_id"] == "audit"]
            == ["dispatch_started", "outcome_unknown", "reconciled"], "Unknown/reconciliation history was lost")
    calls = call_log()
    require(len(calls) == 5 and len({row["idempotency_key"] for row in calls}) == 5, "Submission count/key uniqueness mismatch")
    require([row["part_id"] for row in calls] == ["audit", "inventory", "notes", "summary", "handoff"], "Unexpected execution order")
    return {"dispatch": dispatch, "reconciliation_evidence": evidence, "adapter_calls": calls,
            "audit_replayed": False, "completed_parts": 5, **receiving}


stages = {"start": stage_start, "resume": stage_resume, "hold": stage_hold, "reconcile": stage_reconcile}
if args.phase == "all":
    OUTPUT.mkdir()
    save_new(OUTPUT / "source.json", source_pin)
    processes = []
    for stage in stages:
        command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--phase", stage,
                   "--output", str(OUTPUT)]
        result = subprocess.run(command, cwd=OUTPUT, env=env, capture_output=True, timeout=30)
        bytes_new(OUTPUT / (stage + ".stdout.json"), result.stdout)
        bytes_new(OUTPUT / (stage + ".stderr.log"), result.stderr)
        require(result.returncode == 0, stage + " failed: " + result.stderr.decode(errors="replace"))
        processes.append({"phase": stage, "command": command, "returncode": result.returncode,
                          "stdout_sha256": sha(result.stdout), "stderr_sha256": sha(result.stderr)})
    require(capture_source() == source_pin, "Checkout source changed during this run")
    summary = {"status": "completed", "scope": "authored-local-fixture", "project_id": plan.project_id,
               "plan_digest": plan.digest, "source": source_pin, "processes": processes,
               "completed_parts": 5, "unique_local_adapter_calls": 5, "unknown_acknowledgements": 1,
               "audit_replays": 0, "final_history_events": len(load(OUTPUT / "final-history.json")),
               "provider_calls": 0, "remote_worker_calls": 0,
               "retained_database": "retained.sqlite3", "handoff_artifact": "artifacts/handoff.json",
               "queued_route_reports": [label + "-queued-routes.stdout.json"
                                       for label in ("initial", "unknown", "held", "final")],
               "blocker_reports": [label + "-blockers.stdout.json"
                                   for label in ("initial", "unknown", "held", "final")],
               "qualification": "The local adapter computes file products synchronously. Ultra is an explicitly authorized native route label here; no model inference or provider-effort behavior was exercised."}
    save_new(OUTPUT / "receipt.json", summary)
    print(json.dumps(summary, indent=2))
else:
    require(OUTPUT.is_dir(), "Phase output directory is missing")
    order = list(stages)
    position = order.index(args.phase)
    if position:
        require((OUTPUT / (order[position - 1] + "-receipt.json")).is_file(), "Previous phase receipt is missing")
        require(DB.is_file(), "Retained database is missing")
        with Ledger.open_readonly(DB) as ledger:
            require(inspect_project(ledger, plan.project_id)["plan_digest"] == plan.digest, "Retained plan changed")
    save_new(OUTPUT / (args.phase + "-started.json"), {"phase": args.phase, "pid": os.getpid(), "source_manifest_sha256": source_pin["manifest_sha256"]})
    summary = {"phase": args.phase, "pid": os.getpid(), "source_manifest_sha256": source_pin["manifest_sha256"], **stages[args.phase]()}
    require(capture_source() == source_pin, "Checkout source changed during this phase")
    save_new(OUTPUT / (args.phase + "-receipt.json"), summary)
    print(json.dumps(summary, indent=2))
