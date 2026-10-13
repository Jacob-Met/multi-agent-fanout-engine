"""History publication must leave SQLite's absent sidecar names available."""
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


class HistorySQLitePathTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="fanout-history-path-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.database = self.directory / "history café.sqlite3"
        with Ledger(str(self.database)) as ledger:
            ledger.record_plan(Plan("sample", (Part("pending", "Local fixture."),)))
        self.original = self.database.read_bytes()

    def history(self, *arguments: str, database: Path | None = None):
        return subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.history",
             "--database", str(database or self.database), "--project", "sample",
             *arguments], cwd=ROOT, capture_output=True, timeout=10,
        )

    def assert_reserved(self, destination: Path, *, database: Path | None = None) -> None:
        result = self.history("--output", str(destination), database=database)
        try:
            self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
            self.assertIn(b"cannot write report", result.stderr)
            self.assertIn(b"SQLite sidecar", result.stderr)
            self.assertNotIn(b"Traceback", result.stderr)
            self.assertFalse(os.path.lexists(destination))
            self.assertEqual(self.database.read_bytes(), self.original)
            self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])
        finally:
            # A failing exporter must not poison the next subtest's SQLite read.
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

    def test_missing_selection_precedes_reserved_destination(self) -> None:
        destination = Path(str(self.database) + "-wal")
        for arguments, diagnostic in [
            (("--project", "missing"), b"project_not_found"),
            (("--part", "missing"), b"part_not_found"),
        ]:
            with self.subTest(arguments=arguments):
                result = self.history(*arguments, "--output", str(destination))
                self.assertEqual((result.returncode, result.stdout), (3, b""), result.stderr)
                self.assertIn(diagnostic, result.stderr)
                self.assertNotIn(b"cannot write report", result.stderr)
                self.assertFalse(os.path.lexists(destination))
                self.assertEqual(self.database.read_bytes(), self.original)
        self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])

    def test_invalid_excluded_event_precedes_reserved_destination(self) -> None:
        # The project event is excluded by --part, but must still be validated.
        with closing(sqlite3.connect(self.database)) as connection, connection:
            connection.execute("UPDATE events SET detail_json='not JSON'")
        corrupted = self.database.read_bytes()
        destination = Path(str(self.database) + "-journal")
        result = self.history("--part", "pending", "--output", str(destination))
        self.assertEqual((result.returncode, result.stdout), (2, b""), result.stderr)
        self.assertIn(b"invalid_record", result.stderr)
        self.assertNotIn(b"cannot write report", result.stderr)
        self.assertFalse(os.path.lexists(destination))
        self.assertEqual(self.database.read_bytes(), corrupted)
        self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])

    def test_unrelated_sidecar_suffix_remains_a_valid_new_report(self) -> None:
        unrelated = self.directory / "unrelated.sqlite3"
        unrelated.write_bytes(b"unrelated sentinel")
        destination = Path(str(unrelated) + "-wal")
        expected = self.history("--part", "pending")
        self.assertEqual(expected.returncode, 0, expected.stderr)
        result = self.history("--part", "pending", "--output", str(destination))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        self.assertEqual(destination.read_bytes(), expected.stdout)
        self.assertEqual(unrelated.read_bytes(), b"unrelated sentinel")
        self.assertEqual(self.database.read_bytes(), self.original)
        self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])


if __name__ == "__main__":
    unittest.main()
