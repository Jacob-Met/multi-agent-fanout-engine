"""Receive the final saved comparison step of one public local handoff."""
from __future__ import annotations

import base64
import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_retained_handoff_reviews import (
    Downloads, EXAMPLE, ROOT, digest, files_snapshot, read_json, run_bounded,
)


class RetainedHandoffComparisonsTests(unittest.TestCase):
    def receive(self, output):
        """Run one authored workflow, inspect its comparisons, preserve refusal."""
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
        self.assertEqual((receipt["unique_local_adapter_calls"], receipt["completed_parts"],
                          receipt["audit_replays"], receipt["final_history_events"]), (5, 5, 0, 16))
        self.assertEqual((receipt["provider_calls"], receipt["remote_worker_calls"]), (0, 0))
        source = read_json(output / "source.json")
        self.assertEqual(receipt["source"], source)
        for row in source["files"]:
            self.assertEqual(digest(ROOT / row["path"]), row["sha256"])
        pairs = (("initial", "final"), ("unknown", "held"))
        comparisons = receipt["comparison_reports"]
        self.assertEqual([row["label"] for row in comparisons],
                         [first + "-to-" + second + "-comparison" for first, second in pairs])
        observations = []
        for metadata, (first, second) in zip(comparisons, pairs):
            label = first + "-to-" + second + "-comparison"
            first_path = output / (first + "-inspect.stdout.json")
            second_path = output / (second + "-inspect.stdout.json")
            json_path, html_path = output / (label + ".json"), output / (label + ".html")
            raw = json_path.read_bytes()
            self.assertTrue(raw.endswith(b"\n"))
            report = json.loads(raw)
            self.assertEqual(report["schema"], "fanout.saved-inspection-comparison/1")
            self.assertIs(report["saved_data_only"], True)
            for side, path in (("first", first_path), ("second", second_path)):
                self.assertEqual(report[side], {
                    "input_bytes": len(path.read_bytes()), "input_sha256": digest(path),
                    "document": read_json(path)})
                self.assertEqual(metadata[side + "_inspection"], path.name)
                self.assertEqual(metadata[side + "_inspection_sha256"], digest(path))
            self.assertIs(report["part_order_changed"], False)
            self.assertEqual(report["changed_part_ids"],
                             ["audit", "summary", "handoff"] if first == "initial" else [])
            self.assertEqual(report["same_input_bytes"], first == "unknown")
            self.assertEqual(report["same_saved_values"], first == "unknown")
            left, right = report["first"]["document"], report["second"]["document"]
            self.assertIsNone(left["parts"][0]["task_id"])
            self.assertIsNone(right["parts"][0]["task_id"])
            if first == "initial":
                self.assertEqual((left["state_counts"]["completed"], right["state_counts"]["completed"]),
                                 (2, 5))
                self.assertEqual([row["field"] for row in report["top_level_changes"]],
                                 ["blocked_queued_ids", "queued_ready_ids", "state_counts"])
                self.assertEqual([row["part_id"] for row in report["part_changes"]],
                                 ["audit", "summary", "handoff"])
                for part_id in ("inventory", "notes"):
                    self.assertEqual(next(x for x in left["parts"] if x["id"] == part_id),
                                     next(x for x in right["parts"] if x["id"] == part_id))
            else:
                self.assertEqual(first_path.read_bytes(), second_path.read_bytes())
                self.assertEqual(report["top_level_changes"], [])
                self.assertEqual(report["part_changes"], [])
            document = Downloads()
            document.feed(html_path.read_text(encoding="utf-8"))
            document.close()
            self.assertEqual(len(document.downloads), 1)
            filename, url = document.downloads[0]
            self.assertEqual(filename, "saved-inspection-comparison.json")
            prefix = "data:application/json;base64,"
            self.assertTrue(url.startswith(prefix))
            self.assertEqual(base64.b64decode(url[len(prefix):], validate=True), raw)
            for kind, path in (("json", json_path), ("html", html_path)):
                self.assertEqual(metadata[kind + "_report"], path.name)
                self.assertEqual(metadata[kind + "_sha256"], digest(path))
                invocation = metadata[kind + "_command"]
                self.assertEqual(invocation["command"], [
                    sys.executable, "-B", "-m", "fanout_engine.compare_inspections",
                    "--first", str(first_path), "--second", str(second_path),
                    "--format", kind, "--output", str(path)])
                self.assertEqual((invocation["cwd"], invocation["returncode"]), (str(ROOT), 0))
                for stream in ("stdout", "stderr"):
                    stream_path = output / (label + "-" + kind + "." + stream + ".log")
                    self.assertEqual(stream_path.read_bytes(), b"")
                    self.assertEqual(invocation[stream + "_sha256"], digest(stream_path))
            observations.append({"label": label, "json_sha256": digest(json_path),
                                 "html_sha256": digest(html_path), "changed_part_ids": report["changed_part_ids"]})
        labels = ("initial", "unknown", "held", "final")
        self.assertEqual(receipt["review_reports"], [x + "-review.html" for x in labels])
        self.assertEqual(receipt["queued_route_reports"], [x + "-queued-routes.stdout.json" for x in labels])
        self.assertEqual(receipt["blocker_reports"], [x + "-blockers.stdout.json" for x in labels])
        for phase, label, events in zip(("start", "resume", "hold", "reconcile"), labels, (9, 12, 12, 16)):
            phase_receipt = read_json(output / (phase + "-receipt.json"))
            self.assertEqual(phase_receipt["event_count"], events)
            self.assertEqual(phase_receipt["review_sha256"], digest(output / (label + "-review.html")))
            self.assertEqual(phase_receipt["review_inspection_sha256"],
                             digest(output / (label + "-inspect.stdout.json")))
            for suffix, field in (("queued-routes", "queued_route_command"), ("blockers", "blocker_command")):
                self.assertEqual(phase_receipt[field]["stdout_sha256"],
                                 digest(output / (label + "-" + suffix + ".stdout.json")))
            self.assertTrue(phase_receipt["database_bytes_unchanged_by_readers"])
        self.assertEqual(digest(output / "retained.sqlite3"),
                         read_json(output / "reconcile-receipt.json")["database_sha256"])
        self.assertEqual(read_json(output / "hold-receipt.json")["new_adapter_calls"], 0)
        self.assertTrue(read_json(output / "hold-receipt.json")["retained_history_unchanged"])
        events = read_json(output / "final-history.json")
        self.assertEqual([row["event"] for row in events if row["part_id"] == "audit"],
                         ["dispatch_started", "outcome_unknown", "reconciled"])
        calls = [json.loads(line) for line in
                 (output / "adapter-calls.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["part_id"] for row in calls],
                         ["audit", "inventory", "notes", "summary", "handoff"])
        self.assertEqual(len({row["idempotency_key"] for row in calls}), 5)
        journals = [read_json(path) for path in (output / "adapter-journal").glob("*.json")]
        self.assertEqual(len(journals), 5)
        for journal in journals:
            self.assertEqual(digest(output / journal["artifact"]), journal["artifact_sha256"])
        retained = files_snapshot(output)
        refusal = run_bounded(command)
        self.assertNotEqual(refusal.returncode, 0)
        self.assertEqual(refusal.stdout, b"")
        self.assertEqual(files_snapshot(output), retained)
        self.assertEqual(files_snapshot(ROOT / "fanout_engine"), source_before)
        self.assertEqual(files_snapshot(EXAMPLE), example_before)
        return {"status": "PASS", "command": command, "exit": result.returncode,
                "stdout": result.stdout.decode("utf-8"), "stderr": result.stderr.decode("utf-8"),
                "comparisons": observations, "occupied_output_exit": refusal.returncode,
                "occupied_output_stdout": refusal.stdout.decode("utf-8", errors="replace"),
                "occupied_output_stderr": refusal.stderr.decode("utf-8", errors="replace"),
                "completed_run_files": retained}

    def test_public_workflow_retains_exact_saved_comparisons(self):
        with tempfile.TemporaryDirectory(prefix="fanout-retained-comparisons-") as temporary:
            self.receive(Path(temporary) / "run")


if __name__ == "__main__":
    unittest.main()
