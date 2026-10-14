"""Receive same-run offline pages through the public retained-handoff command."""
from __future__ import annotations

import base64
import hashlib
from html.parser import HTMLParser
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
        if os.name == "posix":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=10)
        try:
            process.communicate(timeout=10)
        finally:
            for stream in (process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


class Downloads(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.downloads = []

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == "a" and "download" in fields:
            self.downloads.append((fields["download"], fields.get("href", "")))


class RetainedHandoffReviewsTests(unittest.TestCase):
    def receive(self, output):
        """Retain one real public run and its occupied-directory refusal."""
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
        self.assertEqual(receipt["plan_digest"],
                         "2c017159028c660378534ec1cb9f1f4bc25abbe2fb01820e0ed472b9c7d99a85")
        self.assertEqual((receipt["unique_local_adapter_calls"], receipt["completed_parts"],
                          receipt["audit_replays"], receipt["final_history_events"]), (5, 5, 0, 16))
        self.assertEqual((receipt["provider_calls"], receipt["remote_worker_calls"]), (0, 0))
        labels = ("initial", "unknown", "held", "final")
        phases = ("start", "resume", "hold", "reconcile")
        self.assertEqual(receipt["review_reports"], [label + "-review.html" for label in labels])
        self.assertEqual(receipt["queued_route_reports"],
                         [label + "-queued-routes.stdout.json" for label in labels])
        self.assertEqual(receipt["blocker_reports"],
                         [label + "-blockers.stdout.json" for label in labels])
        source = read_json(output / "source.json")
        self.assertEqual(receipt["source"], source)
        for item in source["files"]:
            self.assertEqual(digest(ROOT / item["path"]), item["sha256"])
        observations = []
        for index, (phase, label) in enumerate(zip(phases, labels)):
            metadata = read_json(output / (phase + "-receipt.json"))
            inspection_path = output / (label + "-inspect.stdout.json")
            inspection_bytes = inspection_path.read_bytes()
            self.assertTrue(inspection_bytes.endswith(b"\n"))
            state = json.loads(inspection_bytes)
            self.assertEqual(state, read_json(output / (label + "-state.json")))
            page = output / (label + "-review.html")
            document = Downloads()
            document.feed(page.read_text(encoding="utf-8"))
            document.close()
            self.assertEqual(len(document.downloads), 1)
            filename, url = document.downloads[0]
            self.assertEqual(filename, "project-inspection.json")
            prefix = "data:application/json;base64,"
            self.assertTrue(url.startswith(prefix))
            self.assertEqual(base64.b64decode(url[len(prefix):], validate=True), inspection_bytes)
            ready = ["summary"] if label == "initial" else []
            blocked = [] if label == "final" else ["handoff"]
            frontier = ["audit", "summary"] if label == "initial" else (
                [] if label == "final" else ["audit"])
            self.assertEqual(state["state_counts"], {
                "queued": (2, 1, 1, 0)[index], "dispatching": 0, "running": 0,
                "completed": (2, 3, 3, 5)[index], "failed": 0,
                "outcome_unknown": (1, 1, 1, 0)[index]})
            self.assertEqual(state["queued_ready_ids"], ready)
            self.assertEqual(state["blocked_queued_ids"], blocked)
            self.assertEqual([part["id"] for part in state["parts"]],
                             ["audit", "inventory", "notes", "summary", "handoff"])
            audit = state["parts"][0]
            self.assertIsNone(audit["task_id"])
            self.assertEqual(audit["state"], "completed" if label == "final" else "outcome_unknown")
            self.assertEqual(metadata["event_count"], (9, 12, 12, 16)[index])
            self.assertEqual(metadata["source_manifest_sha256"], source["manifest_sha256"])
            self.assertTrue(metadata["database_bytes_unchanged_by_readers"])
            self.assertEqual(metadata["review_report"], page.name)
            self.assertEqual(metadata["review_sha256"], digest(page))
            self.assertEqual(metadata["review_inspection_sha256"], digest(inspection_path))
            invocation = metadata["review_command"]
            self.assertEqual(invocation["command"], [
                sys.executable, "-B", "-m", "fanout_engine.review",
                "--database", str(output / "retained.sqlite3"),
                "--project", receipt["project_id"], "--output", str(page)])
            self.assertEqual((invocation["cwd"], invocation["returncode"]), (str(ROOT), 0))
            for stream in ("stdout", "stderr"):
                raw = output / (label + "-review." + stream + ".log")
                self.assertEqual(raw.read_bytes(), b"")
                self.assertEqual(invocation[stream + "_sha256"], digest(raw))
            routes = read_json(output / (label + "-queued-routes.stdout.json"))
            blockers = read_json(output / (label + "-blockers.stdout.json"))
            self.assertEqual(routes["queued_ready_ids"], ready)
            self.assertEqual(blockers["queued_ready_ids"], ready)
            self.assertEqual([part["id"] for part in blockers["frontier"]], frontier)
            self.assertEqual(metadata["blocker_frontier_ids"], frontier)
            self.assertEqual(blockers["blocked_queued"], [] if label == "final" else [{
                "id": "handoff", "direct_unmet_ids": frontier, "frontier_ids": frontier}])
            for kind, key in (("queued-routes", "queued_route_command"),
                              ("blockers", "blocker_command")):
                self.assertEqual(metadata[key]["returncode"], 0)
                self.assertEqual(metadata[key]["stdout_sha256"],
                                 digest(output / (label + "-" + kind + ".stdout.json")))
                raw = output / (label + "-" + kind + ".stderr.log")
                self.assertEqual(raw.read_bytes(), b"")
                self.assertEqual(metadata[key]["stderr_sha256"], digest(raw))
            observations.append({"phase": phase, "page": page.name,
                                 "page_sha256": digest(page),
                                 "inspection_sha256": digest(inspection_path),
                                 "event_count": metadata["event_count"]})
        self.assertEqual((output / "unknown-inspect.stdout.json").read_bytes(),
                         (output / "held-inspect.stdout.json").read_bytes())
        self.assertEqual((output / "unknown-review.html").read_bytes(),
                         (output / "held-review.html").read_bytes())
        self.assertEqual(read_json(output / "hold-receipt.json")["new_adapter_calls"], 0)
        self.assertTrue(read_json(output / "hold-receipt.json")["retained_history_unchanged"])
        events = read_json(output / "final-history.json")
        self.assertEqual(len(events), 16)
        self.assertEqual([row["event"] for row in events if row["part_id"] == "audit"],
                         ["dispatch_started", "outcome_unknown", "reconciled"])
        calls = [json.loads(line) for line in
                 (output / "adapter-calls.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["part_id"] for row in calls],
                         ["audit", "inventory", "notes", "summary", "handoff"])
        self.assertEqual(len({row["idempotency_key"] for row in calls}), 5)
        for part_id in ("audit", "inventory", "notes", "summary", "handoff"):
            journal = next(row for row in
                           (read_json(path) for path in (output / "adapter-journal").glob("*.json"))
                           if row["part_id"] == part_id)
            self.assertEqual(digest(output / journal["artifact"]), journal["artifact_sha256"])
        before = files_snapshot(output)
        refusal = run_bounded(command)
        self.assertNotEqual(refusal.returncode, 0)
        self.assertEqual(refusal.stdout, b"")
        self.assertEqual(files_snapshot(output), before)
        self.assertEqual(files_snapshot(ROOT / "fanout_engine"), source_before)
        self.assertEqual(files_snapshot(EXAMPLE), example_before)
        return {"status": "PASS", "command": command, "exit": result.returncode,
                "stdout": result.stdout.decode("utf-8"), "stderr": result.stderr.decode("utf-8"),
                "phases": observations, "occupied_output_exit": refusal.returncode,
                "occupied_output_stdout": refusal.stdout.decode("utf-8", errors="replace"),
                "occupied_output_stderr": refusal.stderr.decode("utf-8", errors="replace"),
                "completed_run_files": before}

    def test_public_workflow_retains_exact_offline_phase_reviews(self):
        with tempfile.TemporaryDirectory(prefix="fanout-retained-reviews-") as temporary:
            self.receive(Path(temporary) / "run")


if __name__ == "__main__":
    unittest.main()
