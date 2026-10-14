"""Exercise sample creation with actual child-process text stream encodings."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import Ledger, inspect_project


ROOT = Path(__file__).resolve().parents[1]
CREATOR = ROOT / "examples" / "create_retained_ledger.py"


class SampleCreatorOutputTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="fanout-sample-output-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)

    def run_creator(self, name, encoding):
        environment = os.environ.copy()
        environment["PYTHONIOENCODING"] = encoding
        return subprocess.run(
            [sys.executable, "-S", "-B", str(CREATOR), name],
            cwd=self.directory, env=environment, capture_output=True, timeout=10,
        )

    def assert_created(self, name, encoding, displayed_name, codec):
        result = self.run_creator(name, encoding)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        expected = f"Created authored sample project 'sample' in {displayed_name}{os.linesep}"
        self.assertEqual(result.stdout, expected.encode(codec))
        database = self.directory / name
        self.assertTrue(database.is_file())
        before = database.read_bytes()
        with Ledger.open_readonly(database) as ledger:
            report = inspect_project(ledger, "sample")
            self.assertEqual(report["queued_ready_ids"], ["notes"])
            self.assertEqual(report["blocked_queued_ids"], ["publish"])
            self.assertEqual(ledger.part_state("sample", "source"), "completed")
            self.assertEqual(ledger.part_state("sample", "acknowledge"), "dispatching")
        self.assertEqual(database.read_bytes(), before)
        return database

    def assert_refused(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"sample ledger:", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    def test_cp1252_success_escapes_only_unrepresentable_characters(self):
        for errors in ("strict", "surrogateescape"):
            with self.subTest(errors=errors):
                name = f"{errors}-café-Ω-🚀.sqlite3"
                displayed = f"{errors}-café-\\u03a9-\\U0001f680.sqlite3"
                self.assert_created(name, f"cp1252:{errors}", displayed, "cp1252")

    def test_ascii_and_encodable_cp1252_paths_stay_literal(self):
        for name in ("sample.sqlite3", "café.sqlite3"):
            with self.subTest(name=name):
                self.assert_created(name, "cp1252:strict", name, "cp1252")

    def test_utf8_output_keeps_the_literal_unicode_path(self):
        name = "café-Ω-🚀.sqlite3"
        self.assert_created(name, "utf-8:strict", name, "utf-8")

    def test_configured_output_error_handlers_keep_their_normal_behavior(self):
        cases = (
            ("replace", "replace-café-?-?.sqlite3"),
            ("ignore", "ignore-café--.sqlite3"),
        )
        for errors, displayed in cases:
            with self.subTest(errors=errors):
                name = f"{errors}-café-Ω-🚀.sqlite3"
                self.assert_created(name, f"cp1252:{errors}", displayed, "cp1252")

    def test_existing_unicode_database_is_refused_without_changing_bytes(self):
        name = "existing-Ω.sqlite3"
        database = self.assert_created(name, "utf-8:strict", name, "utf-8")
        before = database.read_bytes()
        self.assert_refused(self.run_creator(name, "cp1252:strict"))
        self.assertEqual(database.read_bytes(), before)

    def test_missing_unicode_parent_is_refused_without_creating_it(self):
        parent = self.directory / "missing-Ω"
        name = str(Path(parent.name) / "sample.sqlite3")
        self.assert_refused(self.run_creator(name, "cp1252:strict"))
        self.assertFalse(parent.exists())
        self.assertEqual(list(self.directory.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
