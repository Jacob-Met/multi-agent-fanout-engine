"""Withdraw one explicitly selected, unsubmitted queued part in an existing ledger."""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys

from .inspect import _write_stdout
from .inspection import InspectionError, inspect_project
from .ledger import Ledger, LedgerError
from .plan import canonical_json


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Permanently withdraw one unsubmitted queued part from an existing fanout ledger.",
        allow_abbrev=False,
    )
    parser.add_argument("--database", type=Path, required=True, help="existing SQLite ledger file")
    parser.add_argument("--project", required=True, help="exact recorded project identifier")
    parser.add_argument("--part", required=True, help="exact queued part identifier")
    parser.add_argument("--source", required=True, help="source of the caller's withdrawal decision")
    parser.add_argument("--locator", required=True, help="retained reference for that decision; not opened")
    parser.add_argument("--finding", required=True, help="reason the authored work is no longer requested")
    args = parser.parse_args(argv)
    evidence = {"source": args.source, "locator": args.locator, "finding": args.finding}
    try:
        # Refuse an unencodable confirmation before opening or changing a ledger.
        content = (canonical_json({
            "project_id": args.project, "part_id": args.part,
            "state": "failed", "event": "queued_withdrawn", "evidence": evidence,
        }) + "\n").encode("utf-8")
        with Ledger.open_existing(args.database) as ledger:
            # Validate the native retained plan, identities and required columns.
            inspect_project(ledger, args.project)
            ledger.withdraw_queued(args.project, args.part, evidence)
    except InspectionError as exc:
        print(f"fanout withdraw: {exc.code}: {exc}", file=sys.stderr)
        return 2
    except (LedgerError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"fanout withdraw: cannot withdraw queued part: {exc}", file=sys.stderr)
        return 2
    try:
        if sys.stdout is None:
            raise OSError("standard output is unavailable")
        _write_stdout(content)
    except (OSError, ValueError) as exc:
        print(
            f"fanout withdraw: withdrawal committed, but cannot write confirmation: {exc}; "
            "inspect project history before retrying.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
