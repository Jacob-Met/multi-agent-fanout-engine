"""Receive the shared SQLite output guard through the blocker CLI."""
from pathlib import Path
import subprocess
import sys
import unittest

import test_inspect_sqlite_paths as sqlite_output_cases


class BlockerSQLiteOutputPathTests(sqlite_output_cases.SQLiteOutputPathTests):
    """Use the donor's unchanged black-box path cases for the new consumer."""

    def inspect(self, destination: Path, *, database: Path | None = None,
                project: str = "sample") -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.blockers",
             "--database", str(database or self.database), "--project", project,
             "--output", str(destination)],
            cwd=sqlite_output_cases.ROOT, capture_output=True, timeout=10,
        )


if __name__ == "__main__":
    unittest.main()
