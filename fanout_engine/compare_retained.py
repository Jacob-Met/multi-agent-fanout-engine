"""Compare a revised draft against one validated retained project."""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys
from typing import Any

from .compare import ComparisonError, _read_plan, _serialize, _write_stdout, compare_plans
from .inspection import InspectionError, inspect_project
from .ledger import Ledger, LedgerError
from .plan import Part, Plan


def compare_retained_plan(ledger: Ledger, project_id: str, candidate: Plan) -> dict[str, Any]:
    """Compare one complete inspected snapshot with a stable candidate Plan.

    Native inspection validates the saved plan, every saved part and its key
    before any comparison is returned. Saved states come from the same SQL
    snapshot. This helper neither records the candidate nor changes task state.
    """
    inspected = inspect_project(ledger, project_id)
    # Reconstruct exact native fields from that one validated report. Using
    # from_dict here would normalize repeated direct-constructor tags and could
    # manufacture a different before digest from the one actually retained.
    before = Plan(inspected["project_id"], tuple(
        Part(row["id"], row["instruction"], tuple(row["depends_on"]), tuple(row["tags"]))
        for row in inspected["parts"]
    ))
    if before.digest != inspected["plan_digest"]:
        raise ComparisonError("retained plan reconstruction changed its native identity")
    report = compare_plans(before, candidate)
    report["retained"] = {
        "project_id": inspected["project_id"],
        "plan_digest": inspected["plan_digest"],
        "state_counts": dict(inspected["state_counts"]),
        "part_states": [{"part_id": row["id"], "state": row["state"]}
                        for row in inspected["parts"]],
    }
    _serialize(report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare a revised JSON plan with one saved project using a read-only ledger.",
        allow_abbrev=False,
    )
    parser.add_argument("--database", type=Path, required=True, help="existing SQLite ledger file")
    parser.add_argument("--project", required=True, help="exact retained project identifier")
    parser.add_argument("--after", type=Path, required=True, help="revised authored plan JSON file")
    args = parser.parse_args(argv)
    try:
        candidate, input_hash = _read_plan(args.after, "after")
        with Ledger.open_readonly(args.database) as ledger:
            report = compare_retained_plan(ledger, args.project, candidate)
        # There is no database-file hash: SQLite's committed view can include
        # WAL bytes. The saved native digest identifies the validated before.
        report["input_sha256"] = {"after": input_hash}
        content = _serialize(report)
    except InspectionError as exc:
        print(f"fanout compare-retained: {exc.code}: {exc}", file=sys.stderr)
        return 3 if exc.code == "project_not_found" else 2
    except RecursionError:
        print("fanout compare-retained: input nesting exceeds comparison limits", file=sys.stderr)
        return 2
    except (LedgerError, sqlite3.Error, ValueError, OSError) as exc:
        print(f"fanout compare-retained: cannot compare plans: {exc}", file=sys.stderr)
        return 2
    try:
        _write_stdout(content)
    except OSError as exc:
        print(f"fanout compare-retained: cannot write report: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
