"""Export a validated recorded native plan without changing its ledger."""
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


def export_plan(ledger: Ledger, project_id: str) -> dict[str, Any]:
    """Return a detached authored plan, validating its retained native identity.

    Runtime part rows, events, evidence and external work are not projected or
    qualified. This is a plan document, not a backup or restoration operation.
    """
    snapshot = ledger.project_snapshot(project_id)
    if snapshot is None:
        raise InspectionError("project_not_found", "project is not in the ledger")
    return _read_plan(snapshot).to_dict()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export one recorded native plan without changing its ledger.",
        allow_abbrev=False,
    )
    parser.add_argument("--database", type=Path, required=True,
                        help="existing SQLite ledger file")
    parser.add_argument("--project", required=True,
                        help="exact recorded project identifier")
    parser.add_argument("--output", type=Path,
                        help="new plan JSON file; otherwise write JSON to stdout")
    args = parser.parse_args(argv)
    try:
        with Ledger.open_readonly(args.database) as ledger:
            document = export_plan(ledger, args.project)
        content = (canonical_json(document) + "\n").encode("utf-8")
    except InspectionError as exc:
        print(f"fanout export-plan: {exc.code}: {exc}", file=sys.stderr)
        return 2
    except (LedgerError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"fanout export-plan: cannot read plan: {exc}", file=sys.stderr)
        return 2
    try:
        if args.output is None:
            _write_stdout(content)
        else:
            _check_output_path(args.database, args.output)
            _publish_new_file(args.output, content)
    except (OSError, PreviewError, ValueError) as exc:
        print(f"fanout export-plan: cannot write plan: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
