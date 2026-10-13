"""Discover projects recorded in an explicitly selected read-only ledger."""
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
from .preview import PreviewError, _publish_new_file


def list_projects(ledger: Ledger) -> dict[str, Any]:
    """List validated recorded plan identities in exact project-ID order.

    Part counts describe the authored plans. Runtime parts, events, references
    and evidence are left to the existing project and history inspectors.
    """
    projects: list[dict[str, Any]] = []
    for snapshot in ledger.project_catalog_snapshot():
        plan = _read_plan(snapshot)
        projects.append({
            "project_id": plan.project_id,
            "plan_digest": plan.digest,
            "part_count": len(plan.parts),
        })
    return {
        "schema_version": 1,
        "project_count": len(projects),
        "projects": projects,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="List saved fanout project identifiers without changing their ledger.",
        allow_abbrev=False,
    )
    parser.add_argument("--database", type=Path, required=True, help="existing SQLite ledger file")
    parser.add_argument("--output", type=Path, help="new catalog file; otherwise write JSON to stdout")
    args = parser.parse_args(argv)
    try:
        with Ledger.open_readonly(args.database) as ledger:
            report = list_projects(ledger)
        content = (canonical_json(report) + "\n").encode("utf-8")
    except InspectionError as exc:
        print(f"fanout projects: {exc.code}: {exc}", file=sys.stderr)
        return 2
    except (LedgerError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"fanout projects: cannot read ledger: {exc}", file=sys.stderr)
        return 2
    try:
        if args.output is None:
            _write_stdout(content)
        else:
            _check_output_path(args.database, args.output)
            _publish_new_file(args.output, content)
    except (OSError, PreviewError, ValueError) as exc:
        print(f"fanout projects: cannot write catalog: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
