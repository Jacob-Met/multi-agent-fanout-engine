"""Explain the unfinished work holding a retained project's queued parts."""
from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
import sys
from typing import Any

from .inspect import _check_output_path, _write_stdout
from .inspection import InspectionError, inspect_project
from .ledger import Ledger, LedgerError
from .plan import canonical_json
from .preview import PreviewError, _publish_new_file


def inspect_blockers(ledger: Ledger, project_id: str) -> dict[str, Any]:
    """Explain queued dependencies from one validated, read-only snapshot.

    Follow only queued unfinished dependencies. Stop at ready queued work or
    any unfinished nonqueued state; completed dependencies cut the traversal.
    These recorded frontiers are observations, not dispatch or retry advice.
    """
    snapshot = inspect_project(ledger, project_id)
    ordered = snapshot["parts"]
    parts = {part["id"]: part for part in ordered}
    position = {part["id"]: index for index, part in enumerate(ordered)}
    memo: dict[str, frozenset[str]] = {}
    blocked: list[dict[str, Any]] = []
    affected: dict[str, list[str]] = {}

    for part in ordered:
        if part["state"] != "queued" or not part["unmet_dependencies"]:
            continue

        # The native inspector has validated an acyclic graph. Expand shared
        # queued subgraphs once, without Python's recursion-depth restriction.
        stack = [(part["id"], False)]
        while stack:
            part_id, expanded = stack.pop()
            if part_id in memo:
                continue
            current = parts[part_id]
            dependencies = [item["id"] for item in current["unmet_dependencies"]]
            if current["state"] == "completed":
                memo[part_id] = frozenset()
            elif current["state"] != "queued" or not dependencies:
                memo[part_id] = frozenset((part_id,))
            elif expanded:
                memo[part_id] = frozenset().union(*(memo[item] for item in dependencies))
            else:
                stack.append((part_id, True))
                stack.extend((item, False) for item in reversed(dependencies) if item not in memo)

        frontier_ids = sorted(memo[part["id"]], key=position.__getitem__)
        blocked.append({
            "id": part["id"],
            "direct_unmet_ids": [item["id"] for item in part["unmet_dependencies"]],
            "frontier_ids": frontier_ids,
        })
        for part_id in frontier_ids:
            affected.setdefault(part_id, []).append(part["id"])

    return {
        "schema_version": 1,
        "project_id": snapshot["project_id"],
        "plan_digest": snapshot["plan_digest"],
        "queued_ready_ids": snapshot["queued_ready_ids"],
        "blocked_queued": blocked,
        "frontier": [
            {
                "id": part["id"],
                "state": part["state"],
                "worker_id": part["worker_id"],
                "task_id": part["task_id"],
                "blocked_queued_ids": affected[part["id"]],
            }
            for part in ordered if part["id"] in affected
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Explain recorded queued dependency blockers without changing or dispatching work.",
        allow_abbrev=False,
    )
    parser.add_argument("--database", type=Path, required=True, help="existing SQLite ledger file")
    parser.add_argument("--project", required=True, help="exact recorded project identifier")
    parser.add_argument("--output", type=Path, help="new report file; otherwise write JSON to stdout")
    args = parser.parse_args(argv)
    try:
        with Ledger.open_readonly(args.database) as ledger:
            report = inspect_blockers(ledger, args.project)
        content = (canonical_json(report) + "\n").encode("utf-8")
    except InspectionError as exc:
        print(f"fanout blockers: {exc.code}: {exc}", file=sys.stderr)
        return 3 if exc.code == "project_not_found" else 2
    except (LedgerError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"fanout blockers: cannot read ledger: {exc}", file=sys.stderr)
        return 2
    try:
        if args.output is None:
            _write_stdout(content)
        else:
            _check_output_path(args.database, args.output)
            _publish_new_file(args.output, content)
    except (OSError, PreviewError, ValueError) as exc:
        destination_note = "" if args.output is None else f" (output: {args.output})"
        print(f"fanout blockers: cannot write report: {exc}{destination_note}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
