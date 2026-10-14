"""Inspect recorded event history without dispatching or changing a ledger."""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import sqlite3
import sys
from typing import Any

from .inspect import _check_output_path, _write_stdout
from .inspection import InspectionError, _decode, _invalid, _read_plan
from .ledger import Ledger, LedgerError
from .plan import PlanError, canonical_json
from .preview import PreviewError, _publish_new_file


def inspect_history(
    ledger: Ledger, project_id: str, *, part_id: str | None = None,
) -> dict[str, Any]:
    """Return the validated recorded timeline, optionally for one exact part.

    Sequence numbers identify recording order, not external execution order.
    Complete project history is validated before the part filter is applied.
    Event names and details remain observations; they are not replay instructions
    or independent proof of an adapter's external effects.
    """
    snapshot = ledger.project_event_snapshot(project_id)
    if snapshot is None:
        raise InspectionError("project_not_found", "project is not in the ledger")
    plan = _read_plan(snapshot)
    known = {part.id for part in plan.parts}
    if part_id is not None and (not isinstance(part_id, str) or part_id not in known):
        raise InspectionError("part_not_found", "part is not in the recorded plan")

    events: list[dict[str, Any]] = []
    previous_seq = 0
    for row in snapshot["events"]:
        seq = row["seq"]
        if not isinstance(seq, int) or isinstance(seq, bool) or seq <= previous_seq:
            raise _invalid("stored events have an invalid recording sequence")
        previous_seq = seq
        if row["project_id"] != plan.project_id:
            raise _invalid(f"event {seq} belongs to a different project")
        if (row["part_id"] is not None
                and (not isinstance(row["part_id"], str) or row["part_id"] not in known)):
            raise _invalid(f"event {seq} references an unknown part")
        if not isinstance(row["event"], str) or not row["event"]:
            raise _invalid(f"event {seq} has a malformed event name")
        if (not isinstance(row["at"], (int, float)) or isinstance(row["at"], bool)
                or not math.isfinite(row["at"])):
            raise _invalid(f"event {seq} has a malformed timestamp")
        detail = _decode(row["detail_json"], f"event {seq} detail")
        events.append({**row, "detail": detail})

    report = {
        "schema_version": 1,
        "project_id": plan.project_id,
        "plan_digest": plan.digest,
        "part_id": part_id,
        "events": [event for event in events
                   if part_id is None or event["part_id"] == part_id],
    }
    try:
        canonical_json(report).encode("utf-8")
    except (PlanError, UnicodeError, RecursionError) as exc:
        raise _invalid("stored events cannot form a finite UTF-8 JSON report") from exc
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect a retained project's recorded event history without changing its ledger.",
        allow_abbrev=False,
    )
    parser.add_argument("--database", type=Path, required=True, help="existing SQLite ledger file")
    parser.add_argument("--project", required=True, help="exact recorded project identifier")
    parser.add_argument("--part", help="show only events recorded for this exact part identifier")
    parser.add_argument("--output", type=Path, help="new report file; otherwise write JSON to stdout")
    args = parser.parse_args(argv)
    try:
        with Ledger.open_readonly(args.database) as ledger:
            report = inspect_history(ledger, args.project, part_id=args.part)
        content = (canonical_json(report) + "\n").encode("utf-8")
    except InspectionError as exc:
        print(f"fanout history: {exc.code}: {exc}", file=sys.stderr)
        return 3 if exc.code in {"project_not_found", "part_not_found"} else 2
    except (LedgerError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"fanout history: cannot read ledger: {exc}", file=sys.stderr)
        return 2
    try:
        if args.output is None:
            _write_stdout(content)
        else:
            _check_output_path(args.database, args.output)
            _publish_new_file(args.output, content)
    except (OSError, PreviewError, ValueError) as exc:
        print(f"fanout history: cannot write report: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
