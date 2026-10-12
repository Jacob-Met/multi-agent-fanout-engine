"""Inspect a retained project from an explicitly selected read-only database."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sqlite3
import sys

from .inspection import InspectionError, inspect_project
from .ledger import Ledger, LedgerError
from .plan import canonical_json


def _write_stdout(content: bytes) -> None:
    try:
        sys.stdout.buffer.write(content)
        sys.stdout.buffer.flush()
    except OSError:
        # A stream can have received a prefix already. Prevent interpreter
        # shutdown from attempting the same failed buffered flush a second time.
        try:
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect one retained fanout project without changing its ledger or dispatching work.",
        allow_abbrev=False,
    )
    parser.add_argument("--database", type=Path, required=True, help="existing SQLite ledger file")
    parser.add_argument("--project", required=True, help="exact recorded project identifier")
    args = parser.parse_args(argv)
    try:
        with Ledger.open_readonly(args.database) as ledger:
            report = inspect_project(ledger, args.project)
        # Complete native validation and encoding precede any success output.
        content = (canonical_json(report) + "\n").encode("utf-8")
    except InspectionError as exc:
        print(f"fanout inspect: {exc.code}: {exc}", file=sys.stderr)
        return 3 if exc.code == "project_not_found" else 2
    except (LedgerError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"fanout inspect: cannot read ledger: {exc}", file=sys.stderr)
        return 2
    try:
        _write_stdout(content)
    except OSError as exc:
        print(f"fanout inspect: cannot write report: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
