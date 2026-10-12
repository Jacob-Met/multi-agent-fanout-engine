"""Exercise retained-plan comparison through actual SQLite and CLI consumers."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import Ledger, Part, Plan
from fanout_engine.compare import ComparisonError, compare_plans
from fanout_engine.compare_retained import compare_retained_plan
from fanout_engine.inspection import InspectionError, inspect_project

ROOT = Path(__file__).resolve().parents[1]


class CompareRetainedTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="retained-comparison-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.database = self.directory / "ledger #?& café.sqlite3"
        self.candidate_path = self.directory / "revised #?.json"
        self.before = Plan("source-review", (
            Part("research", "Read the source.", tags=("b", "a", "b")),
            Part("draft", "Write a draft.", ("research",)),
            Part("uncertain", "Check an earlier attempt."),
            Part("pending", "An admitted attempt awaits acknowledgement."),
        ))
        self.after = Plan("source-review", (
            Part("research", "Read the source.", tags=("b", "a", "b")),
            Part("draft", "Write a draft with citations.", ("research",)),
            Part("review", "Review the draft.", ("draft",)),
        ))
        route = {"model": "local", "effort": "low"}
        with Ledger(str(self.database)) as ledger:
            ledger.record_plan(self.before)
            for part_id in ("research", "uncertain", "pending"):
                ledger.mark_dispatching(self.before.project_id, part_id, "local-worker", route)
            ledger.mark_running(self.before.project_id, "research", "task-research")
            ledger.mark_completed(self.before.project_id, "research", "artifact:source")
            ledger.mark_outcome_unknown(self.before.project_id, "uncertain", {
                "source": "authored fixture", "locator": "attempt:uncertain", "finding": "reply lost",
            })
        self.candidate_path.write_text(json.dumps(self.after.to_dict(), ensure_ascii=False), encoding="utf-8")

    def cli(self, *, database=None, project=None, after=None):
        return subprocess.run(
            [sys.executable, *(["-O"] if not __debug__ else []), "-m", "fanout_engine.compare_retained",
             "--database", str(database or self.database),
             "--project", project or self.before.project_id,
             "--after", str(after or self.candidate_path)],
            cwd=self.directory, env={**os.environ, "PYTHONPATH": str(ROOT)},
            capture_output=True, text=True, encoding="utf-8", timeout=15,
        )

    def test_native_comparison_preserves_exact_tags_keys_and_uncertain_states(self):
        bytes_before = self.database.read_bytes()
        with Ledger.open_readonly(self.database) as ledger:
            original_state = inspect_project(ledger, self.before.project_id)
            events_before = ledger.events(self.before.project_id)
            result = compare_retained_plan(ledger, self.before.project_id, self.after)
            self.assertEqual({k: v for k, v in result.items() if k != "retained"}, compare_plans(self.before, self.after))
            self.assertEqual(result["before"]["plan"], self.before.to_dict())
            self.assertEqual(result["before"]["plan_digest"], self.before.digest)
            self.assertEqual(result["retained"]["state_counts"], original_state["state_counts"])
            self.assertEqual(result["retained"]["part_states"], [
                {"part_id": "research", "state": "completed"},
                {"part_id": "draft", "state": "queued"},
                {"part_id": "uncertain", "state": "outcome_unknown"},
                {"part_id": "pending", "state": "dispatching"},
            ])
            self.assertEqual(ledger.events(self.before.project_id), events_before)
            self.assertEqual(inspect_project(ledger, self.before.project_id), original_state)
        self.assertEqual(self.database.read_bytes(), bytes_before)

    def test_identical_native_plan_and_different_project_remain_distinct(self):
        with Ledger.open_readonly(self.database) as ledger:
            same = compare_retained_plan(ledger, self.before.project_id, self.before)
            self.assertTrue(same["same_plan"])
            self.assertFalse(any(row["changed"] for row in same["idempotency_keys"]))
            other = Plan("different-project", self.before.parts)
            result = compare_retained_plan(ledger, self.before.project_id, other)
            self.assertTrue(result["project_id_changed"])
            self.assertFalse(result["same_plan"])
            self.assertTrue(all(row["changed"] for row in result["idempotency_keys"]))
            self.assertEqual(result["changed_parts"], [])

    def test_real_cli_matches_native_after_parse_and_preserves_both_inputs(self):
        saved_bytes = self.database.read_bytes()
        saved_mtime = self.database.stat().st_mtime_ns
        input_bytes = self.candidate_path.read_bytes()
        filenames = sorted(p.name for p in self.directory.iterdir())
        normalized_candidate = Plan.from_dict(json.loads(input_bytes))
        with Ledger.open_readonly(self.database) as ledger:
            expected = compare_retained_plan(ledger, self.before.project_id, normalized_candidate)
        expected["input_sha256"] = {"after": hashlib.sha256(input_bytes).hexdigest()}
        received = self.cli()
        self.assertEqual(received.returncode, 0, received.stderr)
        self.assertEqual(received.stderr, "")
        self.assertEqual(json.loads(received.stdout), expected)
        self.assertEqual(self.cli().stdout, received.stdout)
        self.assertEqual(self.database.read_bytes(), saved_bytes)
        self.assertEqual(self.database.stat().st_mtime_ns, saved_mtime)
        self.assertEqual(self.candidate_path.read_bytes(), input_bytes)
        self.assertEqual(sorted(p.name for p in self.directory.iterdir()), filenames)

    def test_record_refusal_is_explained_without_modifying_retained_plan(self):
        # Exercise the motivating workflow: the saved project refuses an edited
        # plan, then the operator can inspect differences without retrying it.
        from fanout_engine import LedgerError
        with Ledger(str(self.database)) as ledger:
            with self.assertRaisesRegex(LedgerError, "different plan"):
                ledger.record_plan(self.after)
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["added_part_ids"], ["review"])
        self.assertEqual(report["removed_part_ids"], ["uncertain", "pending"])
        self.assertTrue(all(row["changed"] for row in report["idempotency_keys"]))

    def test_committed_wal_snapshot_excludes_uncommitted_state_changes(self):
        connection = sqlite3.connect(self.database, isolation_level=None)
        self.addCleanup(connection.close)
        self.assertEqual(connection.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
        connection.execute("UPDATE parts SET state='running' WHERE part_id='pending'")
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE parts SET state='failed' WHERE part_id='pending'")
        wal = Path(str(self.database) + "-wal")
        before = (self.database.read_bytes(), wal.read_bytes())
        result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        states = json.loads(result.stdout)["retained"]["part_states"]
        self.assertEqual(next(row["state"] for row in states if row["part_id"] == "pending"), "running")
        self.assertEqual((self.database.read_bytes(), wal.read_bytes()), before)
        self.assertTrue(connection.in_transaction)
        connection.rollback()

    def test_inconsistent_saved_part_refuses_instead_of_comparing_only_header(self):
        with sqlite3.connect(self.database) as connection:
            connection.execute("UPDATE parts SET idempotency_key='wrong' WHERE part_id='pending'")
        before = self.database.read_bytes()
        result = self.cli()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("invalid_record", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.database.read_bytes(), before)

    def test_missing_project_database_and_invalid_candidate_are_distinct(self):
        missing = self.directory / "absent" / "never.sqlite3"
        result = self.cli(database=missing)
        self.assertEqual((result.returncode, result.stdout), (2, ""))
        self.assertFalse(missing.parent.exists())
        result = self.cli(project="missing-project")
        self.assertEqual((result.returncode, result.stdout), (3, ""))
        self.assertIn("project_not_found", result.stderr)
        self.candidate_path.write_text('{"project":"a","project":"b"}', encoding="utf-8")
        result = self.cli()
        self.assertEqual((result.returncode, result.stdout), (2, ""))
        self.assertIn("duplicate JSON", result.stderr)

    def test_comparison_limits_apply_to_retained_and_candidate_plans(self):
        large = Plan("large", tuple(Part(f"p{i}", "Authored") for i in range(257)))
        with Ledger(str(self.database)) as ledger:
            ledger.record_plan(large)
        with Ledger.open_readonly(self.database) as ledger:
            with self.assertRaisesRegex(ComparisonError, "before supports at most 256 parts"):
                compare_retained_plan(ledger, "large", self.after)
            with self.assertRaisesRegex(ComparisonError, "after supports at most 256 parts"):
                compare_retained_plan(ledger, self.before.project_id, large)

    @unittest.skipUnless(Path("/dev/full").exists(), "requires /dev/full")
    def test_failed_report_write_has_nonzero_exit_and_does_not_change_ledger(self):
        before = self.database.read_bytes()
        with open("/dev/full", "wb") as output:
            result = subprocess.run(
                [sys.executable, *(["-O"] if not __debug__ else []), "-m", "fanout_engine.compare_retained",
                 "--database", str(self.database), "--project", self.before.project_id,
                 "--after", str(self.candidate_path)],
                cwd=self.directory, env={**os.environ, "PYTHONPATH": str(ROOT)},
                stdout=output, stderr=subprocess.PIPE, text=True, encoding="utf-8", timeout=15,
            )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("cannot write report", result.stderr)
        self.assertNotIn("Exception ignored", result.stderr)
        self.assertEqual(self.database.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
