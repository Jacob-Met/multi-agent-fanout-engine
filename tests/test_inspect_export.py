"""Receive native inspection reports through create-only file publication."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import Ledger, canonical_json, inspect_project


ROOT = Path(__file__).resolve().parents[1]


def snapshot(path):
    metadata = path.stat()
    return path.read_bytes(), metadata.st_ino, metadata.st_mtime_ns


class InspectExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fanout-inspect-export-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.database = self.directory / "sample.sqlite3"
        created = subprocess.run(
            [sys.executable, "-S", "-B", "examples/create_retained_ledger.py", str(self.database)],
            cwd=ROOT, capture_output=True, timeout=10,
        )
        self.assertEqual(created.returncode, 0, created.stderr)
        with Ledger.open_readonly(self.database) as ledger:
            self.expected = (canonical_json(inspect_project(ledger, "sample")) + "\n").encode("utf-8")
            self.events = ledger.events("sample")

    def command(self, output=None, *, project="sample", database=None):
        arguments = [sys.executable, "-S", "-B", "-m", "fanout_engine.inspect",
                     "--database", str(self.database if database is None else database),
                     "--project", project]
        if output is not None:
            arguments += ["--output", str(output)]
        return arguments

    def run_cli(self, output=None, *, project="sample", database=None, preexec_fn=None):
        return subprocess.run(self.command(output, project=project, database=database),
                              cwd=ROOT, capture_output=True, timeout=10, preexec_fn=preexec_fn)

    def assert_no_stage(self):
        self.assertFalse(any(path.name.startswith(".fanout-")
                             for path in self.directory.iterdir()))

    def assert_output_refused(self, result):
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"fanout inspect: cannot write report:", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        self.assert_no_stage()

    def test_new_file_matches_native_stdout_and_preserves_saved_ledger(self):
        output = self.directory / "report #東京%.json"
        before = snapshot(self.database)
        stdout = self.run_cli()
        self.assertEqual(stdout.returncode, 0, stdout.stderr)
        self.assertEqual(stdout.stdout, self.expected)
        exported = self.run_cli(output)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        self.assertEqual(exported.stdout, b"")
        self.assertEqual(exported.stderr, b"")
        self.assertEqual(output.read_bytes(), self.expected)
        self.assertEqual(snapshot(self.database), before)
        with Ledger.open_readonly(self.database) as ledger:
            self.assertEqual(ledger.events("sample"), self.events)
            self.assertEqual(ledger.part_state("sample", "acknowledge"), "dispatching")
            self.assertEqual(ledger.part_state("sample", "verify"), "outcome_unknown")
        self.assert_no_stage()

    def test_existing_destinations_and_input_aliases_are_preserved(self):
        report = self.directory / "existing.json"
        report.write_bytes(b"previous report\n")
        hardlink = self.directory / "database-hardlink"
        os.link(self.database, hardlink)
        destinations = [report, self.database, hardlink, self.directory]
        if os.name != "nt":
            alias = self.directory / "database-symlink"
            alias.symlink_to(self.database)
            dangling = self.directory / "dangling"
            dangling.symlink_to(self.directory / "absent-target")
            destinations += [alias, dangling]
        if hasattr(os, "mkfifo"):
            fifo = self.directory / "report.pipe"
            os.mkfifo(fifo)
            destinations.append(fifo)
        before = snapshot(self.database)
        for destination in destinations:
            with self.subTest(destination=destination):
                self.assert_output_refused(self.run_cli(destination))
        self.assertEqual(snapshot(self.database), before)
        self.assertEqual(report.read_bytes(), b"previous report\n")
        self.assertFalse((self.directory / "absent-target").exists())

    def test_late_invalid_record_and_missing_project_keep_native_statuses(self):
        output = self.directory / "report.json"
        missing = self.run_cli(output, project="absent")
        self.assertEqual(missing.returncode, 3, missing.stderr)
        self.assertEqual(missing.stdout, b"")
        self.assertIn(b"project_not_found", missing.stderr)
        self.assertFalse(output.exists())
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE parts SET evidence_json='{' WHERE part_id='publish'")
        before = snapshot(self.database)
        invalid = self.run_cli(output)
        self.assertEqual(invalid.returncode, 2, invalid.stderr)
        self.assertEqual(invalid.stdout, b"")
        self.assertIn(b"invalid_record", invalid.stderr)
        self.assertFalse(output.exists())
        self.assertEqual(snapshot(self.database), before)
        self.assert_no_stage()

    def test_missing_database_does_not_create_source_or_output(self):
        missing = self.directory / "missing.sqlite3"
        output = self.directory / "report.json"
        result = self.run_cli(output, database=missing)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"cannot read ledger", result.stderr)
        self.assertFalse(missing.exists())
        self.assertFalse(output.exists())
        self.assert_no_stage()

    def test_missing_output_parent_is_an_output_failure(self):
        output = self.directory / "absent-directory" / "report.json"
        before = snapshot(self.database)
        self.assert_output_refused(self.run_cli(output))
        self.assertFalse(output.parent.exists())
        self.assertEqual(snapshot(self.database), before)

    def test_destination_created_at_publication_wins_without_overwrite(self):
        output = self.directory / "raced.json"
        program = (
            "import pathlib,runpy,sys\n"
            "destination=sys.argv[1]\n"
            "def concurrent_writer(event,args):\n"
            " if event == 'os.link' and str(args[1]) == destination:\n"
            "  pathlib.Path(destination).write_bytes(b'concurrent writer\\n')\n"
            "sys.addaudithook(concurrent_writer)\n"
            "sys.argv=['fanout_engine.inspect',*sys.argv[2:]]\n"
            "runpy.run_module('fanout_engine.inspect',run_name='__main__')\n"
        )
        before = snapshot(self.database)
        result = subprocess.run(
            [sys.executable, "-S", "-B", "-c", program, str(output), *self.command(output)[5:]],
            cwd=ROOT, capture_output=True, timeout=10,
        )
        self.assert_output_refused(result)
        self.assertEqual(output.read_bytes(), b"concurrent writer\n")
        self.assertEqual(snapshot(self.database), before)

    def test_two_actual_exports_publish_once(self):
        output = self.directory / "contended.json"
        before = snapshot(self.database)
        processes = [subprocess.Popen(self.command(output), cwd=ROOT,
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for _ in range(2)]
        results = []
        try:
            for process in processes:
                stdout, stderr = process.communicate(timeout=10)
                results.append((process.returncode, stdout, stderr))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
        self.assertEqual(sorted(result[0] for result in results), [0, 1], results)
        self.assertTrue(all(result[1] == b"" for result in results), results)
        self.assertEqual(output.read_bytes(), self.expected)
        self.assertEqual(snapshot(self.database), before)
        self.assert_no_stage()

    @unittest.skipUnless(os.name == "posix", "requires POSIX file-size limit")
    def test_staging_write_failure_leaves_no_partial_report(self):
        import resource
        import signal

        def limit_output():
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            resource.setrlimit(resource.RLIMIT_FSIZE, (16, 16))

        output = self.directory / "failed.json"
        before = snapshot(self.database)
        self.assert_output_refused(self.run_cli(output, preexec_fn=limit_output))
        self.assertFalse(output.exists())
        self.assertEqual(snapshot(self.database), before)


if __name__ == "__main__":
    unittest.main()
