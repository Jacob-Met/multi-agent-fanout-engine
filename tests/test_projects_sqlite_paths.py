"""Project catalog publication must leave SQLite's absent sidecar names available."""
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
SIDECARS = ("-wal", "-shm", "-journal")


class ProjectsSQLitePathTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="fanout-projects-path-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.database = self.directory / "projects café.sqlite3"
        with Ledger(str(self.database)) as ledger:
            ledger.record_plan(Plan("Alpha", (Part("pending", "Local fixture."),)))
            ledger.record_plan(Plan("zulu", (Part("pending", "Later local fixture."),)))
        self.original = self.database.read_bytes()

    def projects(self, *arguments: str, database: Path | None = None):
        return subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.projects",
             "--database", str(database or self.database),
             *arguments], cwd=ROOT, capture_output=True, timeout=10,
        )

    def assert_reserved(self, destination: Path, *, database: Path | None = None) -> None:
        result = self.projects("--output", str(destination), database=database)
        try:
            self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
            self.assertIn(b"cannot write catalog", result.stderr)
            self.assertIn(b"SQLite sidecar", result.stderr)
            self.assertNotIn(b"Traceback", result.stderr)
            self.assertFalse(os.path.lexists(destination))
            self.assertEqual(self.database.read_bytes(), self.original)
            self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])
        finally:
            # Remove only this fixture output to keep later SQLite reads independent.
            if os.path.lexists(destination):
                destination.unlink()

    def test_absent_sidecars_and_conservative_aliases_are_refused(self) -> None:
        stems = [self.database.name, self.database.name.upper(),
                 unicodedata.normalize("NFD", self.database.name)]
        for stem in stems:
            for suffix in SIDECARS:
                with self.subTest(stem=stem, suffix=suffix):
                    self.assert_reserved(self.directory / (stem + suffix))

    def test_sidecars_of_existing_hardlink_aliases_are_refused(self) -> None:
        alias = self.directory / "hardlink.sqlite3"
        try:
            os.link(self.database, alias)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"hard links unavailable: {exc}")
        for suffix in SIDECARS:
            with self.subTest(suffix=suffix):
                self.assert_reserved(Path(str(alias) + suffix))

    def test_selected_symlink_and_resolved_target_are_reserved(self) -> None:
        alias = self.directory / "selected.sqlite3"
        try:
            alias.symlink_to(self.database)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        for stem in (alias, self.database):
            for suffix in SIDECARS:
                with self.subTest(stem=stem, suffix=suffix):
                    self.assert_reserved(Path(str(stem) + suffix), database=alias)

    def test_missing_source_precedes_reserved_destination(self) -> None:
        missing = self.directory / "missing.sqlite3"
        destination = Path(str(missing) + "-journal")
        result = self.projects("--output", str(destination), database=missing)
        self.assertEqual((result.returncode, result.stdout), (2, b""), result.stderr)
        self.assertIn(b"cannot read ledger", result.stderr)
        self.assertNotIn(b"cannot write catalog", result.stderr)
        self.assertFalse(os.path.lexists(destination))
        self.assertFalse(missing.exists())
        self.assertEqual(self.database.read_bytes(), self.original)
        self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])

    def test_invalid_later_plan_precedes_reserved_destination(self) -> None:
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE projects SET plan_json='{}' WHERE project_id='zulu'")
        corrupted = self.database.read_bytes()
        destination = Path(str(self.database) + "-wal")
        result = self.projects("--output", str(destination))
        self.assertEqual((result.returncode, result.stdout), (2, b""), result.stderr)
        self.assertIn(b"invalid_record", result.stderr)
        self.assertNotIn(b"cannot write catalog", result.stderr)
        self.assertFalse(os.path.lexists(destination))
        self.assertEqual(self.database.read_bytes(), corrupted)
        self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])

    def test_unrelated_sidecar_suffix_remains_a_valid_new_report(self) -> None:
        unrelated = self.directory / "unrelated.sqlite3"
        unrelated.write_bytes(b"unrelated sentinel")
        destination = Path(str(unrelated) + "-wal")
        expected = self.projects()
        self.assertEqual(expected.returncode, 0, expected.stderr)
        result = self.projects("--output", str(destination))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        self.assertEqual(destination.read_bytes(), expected.stdout)
        self.assertEqual(unrelated.read_bytes(), b"unrelated sentinel")
        self.assertEqual(self.database.read_bytes(), self.original)
        self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])


if __name__ == "__main__":
    unittest.main()
