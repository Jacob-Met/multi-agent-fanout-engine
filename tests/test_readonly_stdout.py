"""Actual subprocess regressions for absent stdout in read-only CLIs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import Ledger, Part, Plan

ROOT = Path(__file__).resolve().parents[1]


def close_stdout():
    os.close(1)


@unittest.skipUnless(os.name == "posix", "closed-descriptor startup requires POSIX")
class ReadOnlyStdoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fanout-stdout-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "retained.sqlite3"
        plan = Plan("stdout-fixture", (Part("one", "inert instruction"),))
        with Ledger(str(self.database)) as ledger:
            ledger.record_plan(plan)
        self.plan = self.root / "plan.json"
        self.plan.write_text(json.dumps(plan.to_dict()) + "\n", encoding="utf-8")
        self.routes = self.root / "routes.json"
        self.routes.write_text(json.dumps({
            "catalog": {"fixture": ["low"]},
            "pool": [{"model": "fixture", "effort": "low"}],
        }) + "\n", encoding="utf-8")
        self.commands = {
            "preview": ["--plan", str(self.plan), "--routes", str(self.routes)],
            "inspect": ["--database", str(self.database), "--project", plan.project_id],
            "history": ["--database", str(self.database), "--project", plan.project_id],
            "projects": ["--database", str(self.database)],
        }
        self.inputs = self.fence()

    def fence(self):
        paths = [self.plan, self.routes, self.database]
        paths += [Path(str(self.database) + suffix) for suffix in ("-wal", "-shm", "-journal")]
        return {
            str(path): (path.read_bytes(), path.stat().st_mode, path.stat().st_mtime_ns)
            if path.exists() else None for path in paths
        }

    def invoke(self, command, *, closed=False, stdout=subprocess.PIPE, extra=()):
        return subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine." + command,
             *self.commands[command], *extra],
            cwd=ROOT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            stdout=stdout, stderr=subprocess.PIPE, timeout=8,
            preexec_fn=close_stdout if closed else None,
        )

    def assert_report(self, command, content):
        report = json.loads(content)
        project = (report["plan"]["project"] if command == "preview"
                   else report["projects"][0]["project_id"] if command == "projects"
                   else report["project_id"])
        self.assertEqual(project, "stdout-fixture")

    def test_absent_stdout_has_existing_exit_and_clean_diagnostic_then_recovers(self):
        for command in self.commands:
            with self.subTest(command=command):
                failed = self.invoke(command, closed=True)
                self.assertEqual(failed.returncode, 2 if command == "preview" else 1)
                self.assertEqual(failed.stdout, b"")
                self.assertIn(b"standard output is unavailable", failed.stderr)
                self.assertNotIn(b"Traceback", failed.stderr)
                self.assertNotIn(b"AttributeError", failed.stderr)
                self.assertEqual(len(failed.stderr.splitlines()), 1)
                healthy = self.invoke(command)
                self.assertEqual((healthy.returncode, healthy.stderr), (0, b""))
                self.assert_report(command, healthy.stdout)
                self.assertEqual(self.fence(), self.inputs)

    def test_explicit_file_output_does_not_require_stdout(self):
        for command in ("preview", "inspect", "projects"):
            with self.subTest(command=command):
                output = self.root / (command + "-report.json")
                result = self.invoke(command, closed=True, extra=("--output", str(output)))
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
                self.assert_report(command, output.read_bytes())
                self.assertEqual(self.fence(), self.inputs)

    @unittest.skipUnless(Path("/dev/full").exists(), "requires an actual failing output device")
    def test_existing_stream_write_failure_keeps_clean_exit(self):
        for command in self.commands:
            with self.subTest(command=command):
                with open("/dev/full", "wb") as sink:
                    result = self.invoke(command, stdout=sink)
                self.assertEqual(result.returncode, 2 if command == "preview" else 1)
                self.assertTrue(result.stderr.startswith(("fanout " + command + ": ").encode()))
                self.assertNotIn(b"Traceback", result.stderr)
                self.assertEqual(len(result.stderr.splitlines()), 1)
                self.assertEqual(self.fence(), self.inputs)


if __name__ == "__main__":
    unittest.main()
