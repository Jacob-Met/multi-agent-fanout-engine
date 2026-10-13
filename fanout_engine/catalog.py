"""Discover the exact project identities recorded in an existing ledger."""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys
from typing import Any

from .inspect import _check_output_path, _write_stdout
from .inspection import InspectionError, _read_plan
from .ledger import Ledger, LedgerError
from .plan import canonical_json
from .preview import _publish_new_file


def catalog_projects(ledger: Ledger) -> dict[str, Any]:
    """List validated stored plan headers, without examining retained part state."""
    projects: list[dict[str, Any]] = []
    known: set[str] = set()
    for header in ledger.project_headers():
        plan = _read_plan(header)
        if plan.project_id in known:
            raise InspectionError("invalid_record", "stored project headers contain a repeated identifier")
        known.add(plan.project_id)
        projects.append({
            "project_id": plan.project_id,
            "plan_digest": plan.digest,
            "declared_part_count": len(plan.parts),
        })
    return {"schema_version": 1, "projects": sorted(projects, key=lambda row: row["project_id"])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="List stored fanout plan identities without changing the ledger or dispatching work.",
        allow_abbrev=False,
    )
    parser.add_argument("--database", type=Path, required=True, help="existing SQLite ledger file")
    parser.add_argument("--output", type=Path, help="new catalog file; otherwise write JSON to stdout")
    args = parser.parse_args(argv)
    try:
        with Ledger.open_readonly(args.database) as ledger:
            report = catalog_projects(ledger)
        # All captured headers and the entire report precede any output.
        content = (canonical_json(report) + "\n").encode("utf-8")
    except InspectionError as exc:
        print(f"fanout catalog: {exc.code}: {exc}", file=sys.stderr)
        return 2
    except (LedgerError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"fanout catalog: cannot read ledger: {exc}", file=sys.stderr)
        return 2
    try:
        if args.output is None:
            _write_stdout(content)
        else:
            _check_output_path(args.database, args.output)
            _publish_new_file(args.output, content)
    except (OSError, ValueError) as exc:
        destination_note = "" if args.output is None else f" (output: {args.output})"
        print(f"fanout catalog: cannot write report: {exc}{destination_note}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
