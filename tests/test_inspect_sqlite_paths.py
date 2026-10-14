"""Keep report exports away from SQLite's reserved sidecar names."""
from __future__ import annotations

from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
import unittest

from fanout_engine import Ledger, Part, Plan

ROOT = Path(__file__).resolve().parents[1]


class SQLiteOutputPathTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="fanout-sqlite-output-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.database = self.directory / "ledger café.sqlite3"
        with Ledger(str(self.database)) as ledger:
            ledger.record_plan(Plan("sample", (Part("notes", "Authored local work."),)))
        self.original = self.database.read_bytes()

    def inspect(self, destination: Path, *, database: Path | None = None,
                project: str = "sample") -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.inspect",
             "--database", str(database or self.database), "--project", project,
             "--output", str(destination)],
            cwd=ROOT, capture_output=True, timeout=10,
        )

    def assert_reserved(self, destination: Path, *, database: Path | None = None) -> None:
        result = self.inspect(destination, database=database)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"SQLite sidecar", result.stderr)
        self.assertFalse(os.path.lexists(destination))
        self.assertEqual(self.database.read_bytes(), self.original)
        self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])

    def test_absent_reserved_sidecars_are_refused(self) -> None:
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                self.assert_reserved(Path(str(self.database) + suffix))

    def test_absent_case_and_unicode_aliases_are_refused(self) -> None:
        stems = [self.database.name.upper(),
                 unicodedata.normalize("NFD", self.database.name)]
        for stem in stems:
            for suffix in ("-WAL", "-shm", "-journal"):
                with self.subTest(stem=stem, suffix=suffix):
                    self.assert_reserved(self.directory / (stem + suffix))

    def test_sidecars_of_a_hard_linked_database_name_are_refused(self) -> None:
        alias = self.directory / "hard-link.sqlite3"
        os.link(self.database, alias)
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                self.assert_reserved(Path(str(alias) + suffix))

    def test_selected_symlink_and_target_names_are_both_reserved(self) -> None:
        alias = self.directory / "selected-link.sqlite3"
        try:
            alias.symlink_to(self.database)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        for stem in (alias, self.database):
            for suffix in ("-wal", "-shm", "-journal"):
                with self.subTest(stem=stem, suffix=suffix):
                    self.assert_reserved(Path(str(stem) + suffix), database=alias)

    def test_native_validation_precedes_destination_refusal(self) -> None:
        reserved = Path(str(self.database) + "-wal")
        missing = self.inspect(reserved, project="absent")
        self.assertEqual(missing.returncode, 3, missing.stderr)
        self.assertEqual(missing.stdout, b"")
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE projects SET plan_json='not JSON'")
        invalid = self.inspect(reserved)
        self.assertEqual(invalid.returncode, 2, invalid.stderr)
        self.assertEqual(invalid.stdout, b"")
        self.assertFalse(os.path.lexists(reserved))
        self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])

    def test_fresh_report_still_uses_the_accepted_publisher(self) -> None:
        destination = self.directory / "report.json"
        result = self.inspect(destination)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")
        original = destination.read_bytes()
        self.assertTrue(original.endswith(b"\n"))
        self.assertIn(b'"project_id":"sample"', original)
        occupied = self.inspect(destination)
        self.assertEqual(occupied.returncode, 1, occupied.stderr)
        self.assertEqual(destination.read_bytes(), original)
        self.assertEqual(self.database.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()

