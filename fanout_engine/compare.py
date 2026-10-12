"""Compare two authored native plans without recording or dispatching work."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys
from typing import Any

from .plan import Part, Plan, canonical_json, strict_json_loads

MAX_PLAN_BYTES = 1024 * 1024
MAX_PARTS = 256
MAX_REPORT_BYTES = 4 * 1024 * 1024


class ComparisonError(ValueError):
    """Raised when a plan comparison cannot provide a complete native report."""


def _serialize(report: dict[str, Any]) -> bytes:
    content = (canonical_json(report) + "\n").encode("utf-8")
    if len(content) > MAX_REPORT_BYTES:
        raise ComparisonError("comparison report exceeds the 4 MiB consumer limit")
    return content


def _snapshot(plan: Plan, label: str) -> Plan:
    if not isinstance(plan, Plan):
        raise ComparisonError(f"{label} must be a native Plan")
    if len(plan.parts) > MAX_PARTS:
        raise ComparisonError(f"{label} supports at most 256 parts")
    # Capture exact constructor semantics, including repeated tags. Re-parsing
    # through from_dict would normalize them. A mutated Part-like object must
    # not make the recorded digest describe a different captured plan.
    captured = Plan(plan.project_id, tuple(
        Part(part.id, part.instruction, part.depends_on, part.tags)
        for part in plan.parts
    ))
    if captured.digest != plan.digest:
        raise ComparisonError(f"{label} Plan has changed since validation")
    return captured


def compare_plans(before: Plan, after: Plan) -> dict[str, Any]:
    """Describe exact native identity and payload changes between stable plans.

    The comparison is directional. Added/common keys follow the after plan's
    declaration order; removed keys follow the before plan's declaration order.
    It contains no stored state, completion evidence or permission to reuse keys.
    """
    before = _snapshot(before, "before")
    after = _snapshot(after, "after")
    before_document = before.to_dict()
    after_document = after.to_dict()
    before_parts = {part["id"]: part for part in before_document["parts"]}
    after_parts = {part["id"]: part for part in after_document["parts"]}
    added = [part_id for part_id in after_parts if part_id not in before_parts]
    removed = [part_id for part_id in before_parts if part_id not in after_parts]
    changed = []
    for part_id, part in after_parts.items():
        if part_id in before_parts:
            fields = [name for name in ("instruction", "depends_on", "tags")
                      if before_parts[part_id][name] != part[name]]
            if fields:
                changed.append({"part_id": part_id, "fields": fields})

    keys = []
    for part_id in [*after_parts, *removed]:
        old_key = before.idempotency_key(part_id) if part_id in before_parts else None
        new_key = after.idempotency_key(part_id) if part_id in after_parts else None
        keys.append({"part_id": part_id, "before": old_key, "after": new_key,
                     "changed": old_key != new_key})
    report = {
        "schema_version": 1,
        "before": {"plan": before_document, "plan_digest": before.digest},
        "after": {"plan": after_document, "plan_digest": after.digest},
        "same_plan": before_document == after_document,
        "project_id_changed": before.project_id != after.project_id,
        "part_order_changed": list(before_parts) != list(after_parts),
        "added_part_ids": added,
        "removed_part_ids": removed,
        "changed_parts": changed,
        "idempotency_keys": keys,
    }
    _serialize(report)
    return report


def _read_plan(path: Path, label: str) -> tuple[Plan, str]:
    # Open without waiting on a FIFO, then verify the opened object itself.
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise ComparisonError(f"{label} input must be a regular file")
        if metadata.st_size > MAX_PLAN_BYTES:
            raise ComparisonError(f"{label} input exceeds the 1 MiB consumer limit")
        content = source.read(MAX_PLAN_BYTES + 1)
    if len(content) > MAX_PLAN_BYTES:
        raise ComparisonError(f"{label} input exceeds the 1 MiB consumer limit")
    value = strict_json_loads(content.decode("utf-8"))
    if isinstance(value, dict) and isinstance(value.get("parts"), list):
        if len(value["parts"]) > MAX_PARTS:
            raise ComparisonError(f"{label} supports at most 256 parts")
    return Plan.from_dict(value), hashlib.sha256(content).hexdigest()


def _write_stdout(content: bytes) -> None:
    try:
        sys.stdout.buffer.write(content)
        sys.stdout.buffer.flush()
    except OSError:
        # Avoid another failed buffered flush during interpreter shutdown.
        try:
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare two authored plans and their native keys without opening a Ledger or dispatching work.",
        allow_abbrev=False,
    )
    parser.add_argument("--before", type=Path, required=True, help="original authored plan JSON file")
    parser.add_argument("--after", type=Path, required=True, help="revised authored plan JSON file")
    args = parser.parse_args(argv)
    try:
        before, before_hash = _read_plan(args.before, "before")
        after, after_hash = _read_plan(args.after, "after")
        report = compare_plans(before, after)
        report["input_sha256"] = {"before": before_hash, "after": after_hash}
        content = _serialize(report)
    except RecursionError:
        print("fanout compare: input nesting exceeds comparison limits", file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print(f"fanout compare: cannot compare plans: {exc}", file=sys.stderr)
        return 2
    try:
        _write_stdout(content)
    except OSError as exc:
        print(f"fanout compare: cannot write report: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
