"""Receive the existing failure example through a saved SQLite ledger."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fanout_engine import Ledger, inspect_project


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "failure_flow.py"
PROJECT = "local-failure-demo"


class RetainedFailureExampleTests(unittest.TestCase):
    def run_example(self, *arguments):
        return subprocess.run(
            [sys.executable, "-B", str(EXAMPLE), *map(str, arguments)],
            capture_output=True, text=True, timeout=15, check=False,
        )

    def check_report(self, report):
        self.assertEqual(set(report), {"first_dispatch", "next_dispatch", "local_submissions",
                                       "child_returncode", "child_stdout", "child_stderr",
                                       "events", "project"})
        self.assertEqual(report["local_submissions"], 1)
        self.assertEqual(report["child_returncode"], 7)
        self.assertEqual(report["child_stdout"], "")
        self.assertEqual(report["child_stderr"], "authored fixture failure\n")
        self.assertEqual(report["first_dispatch"]["started"], ["build"])
        self.assertEqual(report["next_dispatch"]["started"], [])
        self.assertEqual(report["next_dispatch"]["not_ready"], ["verify"])
        self.assertEqual(report["project"]["state_counts"]["failed"], 1)
        self.assertEqual(report["project"]["blocked_queued_ids"], ["verify"])
        self.assertEqual([row["event"] for row in report["events"]],
                         ["dispatch_started", "dispatch_accepted", "failed"])
        failed = report["project"]["parts"][0]
        self.assertEqual(report["events"][-1]["detail"], failed["evidence"])
        self.assertEqual(failed["task_id"], failed["evidence"]["locator"])
        self.assertIn("terminal exit 7", failed["evidence"]["finding"])

    def test_default_keeps_the_existing_local_inmemory_result(self):
        result = self.run_example()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.check_report(json.loads(result.stdout))

    def test_explicit_file_is_reopened_and_matches_existing_inspection_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "failed 東京.sqlite3"
            result = self.run_example("--database", database)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(database.is_file(), "the requested retained database must exist")
            self.assertEqual(result.stderr, "")
            report = json.loads(result.stdout)
            self.check_report(report)
            with Ledger.open_readonly(database) as ledger:
                self.assertEqual(report["project"], inspect_project(ledger, PROJECT))
                self.assertEqual(report["events"], ledger.events(PROJECT, "build"))
            saved = database.read_bytes()
            inspected = subprocess.run(
                [sys.executable, "-B", "-m", "fanout_engine.inspect", "--database", str(database),
                 "--project", PROJECT], cwd=ROOT,
                capture_output=True, text=True, timeout=10, check=False,
            )
            self.assertEqual(inspected.returncode, 0, inspected.stderr)
            self.assertEqual(json.loads(inspected.stdout), report["project"])
            self.assertEqual(database.read_bytes(), saved)

    def test_existing_file_directory_and_symlinks_refuse_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "existing.sqlite3"
            existing.write_bytes(b"existing bytes must remain exact\x00\xff")
            folder = root / "existing-directory"
            folder.mkdir()
            target = root / "target.sqlite3"
            target.write_bytes(b"symlink target remains exact")
            link = root / "link.sqlite3"
            dangling = root / "dangling.sqlite3"
            try:
                link.symlink_to(target)
                dangling.symlink_to(root / "absent-target.sqlite3")
                destinations = (existing, folder, link, dangling)
            except OSError:
                destinations = (existing, folder)
            before = {p.name: p.read_bytes() for p in (existing, target)}
            for destination in destinations:
                with self.subTest(destination=destination.name):
                    result = self.run_example("--database", destination)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertNotIn("Traceback", result.stderr)
            self.assertEqual({p.name: p.read_bytes() for p in (existing, target)}, before)
            self.assertTrue(folder.is_dir())
            if link.is_symlink():
                self.assertEqual(link.readlink(), target)
            if dangling.is_symlink():
                self.assertEqual(dangling.readlink(), root / "absent-target.sqlite3")
            self.assertFalse((root / "absent-target.sqlite3").exists())

    def test_missing_parent_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "missing" / "example.sqlite3"
            result = self.run_example("--database", database)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertFalse(database.parent.exists())
            self.assertNotIn("Traceback", result.stderr)

    def test_argument_errors_refuse_before_creating_the_requested_file(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "new.sqlite3"
            for suffix in (("--typo",), ("--dat", "other"), ("unexpected",)):
                with self.subTest(suffix=suffix):
                    result = self.run_example("--database", database, *suffix)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertFalse(database.exists())
            missing_value = self.run_example("--database")
            self.assertEqual(missing_value.returncode, 2)
            self.assertEqual(missing_value.stdout, "")

    def test_help_explains_saved_mode_without_running_the_child(self):
        result = self.run_example("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--database", result.stdout)
        self.assertIn("usage:", result.stdout)
        self.assertNotIn("local_submissions", result.stdout)

    def test_failure_and_interruption_retain_an_honest_partial_ledger(self):
        spec = importlib.util.spec_from_file_location("retained_failure_flow", EXAMPLE)
        example = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(example)
        for error, expected_code in ((sqlite3.OperationalError("fixture result write refused"), 2),
                                     (KeyboardInterrupt(), 130)):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                database = Path(directory) / "interrupted.sqlite3"
                stderr = io.StringIO()
                with patch.object(example.Ledger, "mark_failed", side_effect=error), \
                        contextlib.redirect_stderr(stderr):
                    code = example.main(["--database", str(database)])
                self.assertEqual(code, expected_code)
                self.assertIn("retained", stderr.getvalue().lower())
                self.assertIn(str(database), stderr.getvalue())
                self.assertTrue(database.is_file())
                with Ledger.open_readonly(database) as retained:
                    self.assertEqual(retained.part_state(PROJECT, "build"), "running")
                    self.assertEqual([event["event"] for event in retained.events(PROJECT, "build")],
                                     ["dispatch_started", "dispatch_accepted"])

    def test_interruption_after_spawn_collects_the_owned_child(self):
        spec = importlib.util.spec_from_file_location("interrupted_failure_flow", EXAMPLE)
        example = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(example)
        spawned = []

        def start_sleeping_child(hub, part, **kwargs):
            hub.process = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )
            spawned.append(hub.process)
            hub.submissions += 1
            return {"task_id": f"local-child:{hub.process.pid}"}

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "interrupted-after-spawn.sqlite3"
            stderr = io.StringIO()
            try:
                with patch.object(example.LocalFailureHub, "submit", start_sleeping_child), \
                        patch.object(example.Ledger, "mark_running", side_effect=KeyboardInterrupt()), \
                        contextlib.redirect_stderr(stderr):
                    code = example.main(["--database", str(database)])
                self.assertEqual(code, 130)
                self.assertEqual(len(spawned), 1)
                self.assertIsNotNone(spawned[0].poll(), "the invocation must collect its own interrupted child")
                self.assertIn("retained", stderr.getvalue().lower())
                with Ledger.open_readonly(database) as retained:
                    self.assertEqual(retained.part_state(PROJECT, "build"), "dispatching")
                    self.assertEqual([event["event"] for event in retained.events(PROJECT, "build")],
                                     ["dispatch_started"])
            finally:
                for child in spawned:
                    if child.poll() is None:
                        child.kill()
                        child.communicate(timeout=10)


if __name__ == "__main__":
    unittest.main()
