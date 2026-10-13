"""Receive queued-route captures through the documented retained-handoff command."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "retained_handoff"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files_snapshot(root):
    return {path.relative_to(root).as_posix():
            (digest(path), path.stat().st_mode, path.stat().st_mtime_ns)
            for path in root.rglob("*") if path.is_file()}


def run_bounded(command):
    env = {key: value for key, value in os.environ.items()
           if key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE", "PYTHONSTARTUP"}}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=os.name == "posix")
    try:
        stdout, stderr = process.communicate(timeout=120)
    except subprocess.TimeoutExpired:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


class RetainedHandoffQueuedRoutesTests(unittest.TestCase):
    def test_public_workflow_captures_retained_routes_and_preserves_refusal(self):
        with tempfile.TemporaryDirectory(prefix="fanout-retained-routes-") as temporary:
            output = Path(temporary) / "run"
            command = [sys.executable, "-I", "-B", str(EXAMPLE / "run_consumer.py"),
                       "--output", str(output)]
            result = run_bounded(command)
            self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
            self.assertEqual(result.stderr, b"")
            receipt = read_json(output / "receipt.json")
            self.assertEqual(json.loads(result.stdout), receipt)
            self.assertEqual(receipt["unique_local_adapter_calls"], 5)
            self.assertEqual(receipt["audit_replays"], 0)
            self.assertEqual(receipt["final_history_events"], 16)
            self.assertEqual((receipt["provider_calls"], receipt["remote_worker_calls"]), (0, 0))
            labels = ("initial", "unknown", "held", "final")
            phases = ("start", "resume", "hold", "reconcile")
            names = [label + "-queued-routes.stdout.json" for label in labels]
            self.assertEqual(receipt["queued_route_reports"], names)
            source = read_json(output / "source.json")
            self.assertEqual(receipt["source"], source)
            for item in source["files"]:
                self.assertEqual(digest(ROOT / item["path"]), item["sha256"])
            for phase, label, name in zip(phases, labels, names):
                with self.subTest(phase=phase):
                    metadata = read_json(output / (phase + "-receipt.json"))
                    state = read_json(output / (label + "-state.json"))
                    report = read_json(output / name)
                    expected_ready = ["summary"] if phase == "start" else []
                    self.assertEqual(metadata["source_manifest_sha256"], source["manifest_sha256"])
                    self.assertEqual(metadata["queued_route_report"], name)
                    self.assertEqual(metadata["queued_route_ready_ids"], expected_ready)
                    self.assertEqual(report["schema_version"], 1)
                    for key in ("project_id", "plan_digest", "state_counts",
                                "queued_ready_ids", "blocked_queued_ids"):
                        self.assertEqual(report[key], state[key])
                    self.assertEqual(report["queued_ready_ids"], expected_ready)
                    self.assertEqual(report["blocked_queued_ids"],
                                     [] if phase == "reconcile" else ["handoff"])
                    self.assertEqual(report["routing_input_sha256"],
                                     digest(EXAMPLE / "fixtures" / "routes.json"))
                    self.assertIsNone(report["configured_step_up"])
                    self.assertEqual(report["parts"], [
                        {key: row[key] for key in ("id", "state", "unmet_dependencies")}
                        for row in state["parts"]])
                    if phase == "start":
                        stored = next(row for row in state["parts"] if row["id"] == "summary")
                        self.assertEqual(report["routes"], [{
                            "part_id": "summary", "route": {"model": "fixture-local", "effort": "low"},
                            "route_source": "pool", "idempotency_key": stored["idempotency_key"]}])
                    else:
                        self.assertEqual(report["routes"], [])
                    invocation = metadata["queued_route_command"]
                    self.assertEqual(invocation["command"], [
                        sys.executable, "-B", "-m", "fanout_engine.queued_routes",
                        "--database", str(output / "retained.sqlite3"), "--project", receipt["project_id"],
                        "--routes", str(EXAMPLE / "fixtures" / "routes.json")])
                    self.assertEqual(invocation["cwd"], str(ROOT))
                    self.assertEqual(invocation["returncode"], 0)
                    self.assertEqual(invocation["stdout_sha256"], digest(output / name))
                    stderr_path = output / (label + "-queued-routes.stderr.log")
                    self.assertEqual(stderr_path.read_bytes(), b"")
                    self.assertEqual(invocation["stderr_sha256"], digest(stderr_path))
                    self.assertTrue(metadata["database_bytes_unchanged_by_readers"])
            events = read_json(output / "final-history.json")
            self.assertEqual(len(events), 16)
            self.assertEqual([row["event"] for row in events if row["part_id"] == "audit"],
                             ["dispatch_started", "outcome_unknown", "reconciled"])
            calls = [json.loads(line) for line in (output / "adapter-calls.jsonl").read_text().splitlines()]
            self.assertEqual([row["part_id"] for row in calls],
                             ["audit", "inventory", "notes", "summary", "handoff"])
            self.assertEqual(len({row["idempotency_key"] for row in calls}), 5)
            before = files_snapshot(output)
            refusal = run_bounded(command)
            self.assertNotEqual(refusal.returncode, 0)
            self.assertEqual(files_snapshot(output), before)


if __name__ == "__main__":
    unittest.main()
