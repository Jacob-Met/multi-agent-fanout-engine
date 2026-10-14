"""Receive blocker captures through the documented retained-handoff command."""
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


class RetainedHandoffBlockersTests(unittest.TestCase):
    def receive(self, output):
        """Run the maintained receiving body into a caller-owned fresh directory."""
        source_before = files_snapshot(ROOT / "fanout_engine")
        example_before = files_snapshot(EXAMPLE)
        command = [sys.executable, "-I", "-B", str(EXAMPLE / "run_consumer.py"),
                   "--output", str(output)]
        result = run_bounded(command)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        self.assertEqual(result.stderr, b"")
        receipt = read_json(output / "receipt.json")
        self.assertEqual(json.loads(result.stdout), receipt)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["scope"], "authored-local-fixture")
        self.assertEqual(receipt["project_id"], "fixture-handoff-51df5b72e832")
        self.assertEqual(receipt["unique_local_adapter_calls"], 5)
        self.assertEqual(receipt["completed_parts"], 5)
        self.assertEqual(receipt["audit_replays"], 0)
        self.assertEqual(receipt["final_history_events"], 16)
        self.assertEqual((receipt["provider_calls"], receipt["remote_worker_calls"]), (0, 0))
        labels = ("initial", "unknown", "held", "final")
        phases = ("start", "resume", "hold", "reconcile")
        names = [label + "-blockers.stdout.json" for label in labels]
        self.assertEqual(receipt["blocker_reports"], names)
        self.assertEqual(receipt["queued_route_reports"],
                         [label + "-queued-routes.stdout.json" for label in labels])
        source = read_json(output / "source.json")
        self.assertEqual(receipt["source"], source)
        for item in source["files"]:
            self.assertEqual(digest(ROOT / item["path"]), item["sha256"])
        observations = []
        for phase, label, name in zip(phases, labels, names):
            metadata = read_json(output / (phase + "-receipt.json"))
            state = read_json(output / (label + "-state.json"))
            report = read_json(output / name)
            ready = ["summary"] if phase == "start" else []
            frontier_ids = ["audit", "summary"] if phase == "start" else (
                [] if phase == "reconcile" else ["audit"])
            frontier = [] if phase == "reconcile" else [{
                "id": "audit", "state": "outcome_unknown",
                "worker_id": "local-file-worker-audit", "task_id": None,
                "blocked_queued_ids": ["handoff"]}]
            if phase == "start":
                frontier.append({"id": "summary", "state": "queued", "worker_id": None,
                                 "task_id": None, "blocked_queued_ids": ["handoff"]})
            expected = {
                "schema_version": 1, "project_id": receipt["project_id"],
                "plan_digest": receipt["plan_digest"], "queued_ready_ids": ready,
                "blocked_queued": [] if phase == "reconcile" else [{
                    "id": "handoff", "direct_unmet_ids": frontier_ids,
                    "frontier_ids": frontier_ids}],
                "frontier": frontier,
            }
            self.assertEqual(report, expected)
            expected_bytes = (json.dumps(expected, ensure_ascii=False, sort_keys=True,
                                         separators=(",", ":")) + "\n").encode("utf-8")
            self.assertEqual((output / name).read_bytes(), expected_bytes)
            self.assertEqual(metadata["source_manifest_sha256"], source["manifest_sha256"])
            self.assertEqual(metadata["blocker_report"], name)
            self.assertEqual(metadata["blocker_frontier_ids"], frontier_ids)
            invocation = metadata["blocker_command"]
            self.assertEqual(invocation["command"], [
                sys.executable, "-B", "-m", "fanout_engine.blockers",
                "--database", str(output / "retained.sqlite3"),
                "--project", receipt["project_id"]])
            self.assertEqual(invocation["cwd"], str(ROOT))
            self.assertEqual(invocation["returncode"], 0)
            self.assertEqual(invocation["stdout_sha256"], digest(output / name))
            stderr_path = output / (label + "-blockers.stderr.log")
            self.assertEqual(stderr_path.read_bytes(), b"")
            self.assertEqual(invocation["stderr_sha256"], digest(stderr_path))
            self.assertTrue(metadata["database_bytes_unchanged_by_readers"])
            self.assertEqual(state["queued_ready_ids"], ready)
            self.assertEqual(state["blocked_queued_ids"],
                             [] if phase == "reconcile" else ["handoff"])
            routes = read_json(output / (label + "-queued-routes.stdout.json"))
            self.assertEqual(routes["queued_ready_ids"], ready)
            self.assertEqual(metadata["queued_route_ready_ids"], ready)
            observations.append({"phase": phase, "frontier_ids": frontier_ids,
                                 "report_sha256": digest(output / name),
                                 "event_count": metadata["event_count"]})
        self.assertEqual([row["event_count"] for row in observations], [9, 12, 12, 16])
        events = read_json(output / "final-history.json")
        self.assertEqual(len(events), 16)
        self.assertEqual([row["event"] for row in events if row["part_id"] == "audit"],
                         ["dispatch_started", "outcome_unknown", "reconciled"])
        calls = [json.loads(line) for line in
                 (output / "adapter-calls.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["part_id"] for row in calls],
                         ["audit", "inventory", "notes", "summary", "handoff"])
        self.assertEqual(len({row["idempotency_key"] for row in calls}), 5)
        self.assertEqual(read_json(output / "hold-receipt.json")["new_adapter_calls"], 0)
        self.assertTrue(read_json(output / "hold-receipt.json")["retained_history_unchanged"])
        before = files_snapshot(output)
        refusal = run_bounded(command)
        self.assertNotEqual(refusal.returncode, 0)
        self.assertEqual(files_snapshot(output), before)
        self.assertEqual(files_snapshot(ROOT / "fanout_engine"), source_before)
        self.assertEqual(files_snapshot(EXAMPLE), example_before)
        return {"status": "PASS", "command": command, "exit": result.returncode,
                "stdout": result.stdout.decode("utf-8"), "stderr": result.stderr.decode("utf-8"),
                "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
                "phases": observations, "occupied_output_exit": refusal.returncode,
                "occupied_output_stdout": refusal.stdout.decode("utf-8", errors="replace"),
                "occupied_output_stderr": refusal.stderr.decode("utf-8", errors="replace"),
                "completed_run_files": before}

    def test_public_workflow_captures_blockers_without_replaying_work(self):
        with tempfile.TemporaryDirectory(prefix="fanout-retained-blockers-") as temporary:
            self.receive(Path(temporary) / "run")


if __name__ == "__main__":
    unittest.main()
