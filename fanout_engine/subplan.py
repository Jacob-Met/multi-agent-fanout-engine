"""Produce a new native Plan from explicit parts and their prerequisites."""
from __future__ import annotations

import argparse
from collections.abc import Sequence
import os
from pathlib import Path
import stat
import sys

from .plan import Part, Plan, canonical_json, strict_json_loads

MAX_PLAN_BYTES = 1024 * 1024
MAX_SOURCE_PARTS = 4096
MAX_RESULT_PARTS = 256


class SubplanError(ValueError):
    """Raised when an authored subplan cannot be produced completely."""


def _serialize(plan: Plan) -> bytes:
    content = (canonical_json(plan.to_dict()) + "\n").encode("utf-8")
    if len(content) > MAX_PLAN_BYTES:
        raise SubplanError("resulting plan exceeds the 1 MiB consumer limit")
    return content


def select_subplan(plan: Plan, part_ids: Sequence[str], project_id: str) -> Plan:
    """Copy selected parts and all ancestors, retaining source declaration order.

    The new project identifier must differ from the source. This produces an
    authored plan only; no completion, routing or dispatch state is transferred.
    """
    if not isinstance(plan, Plan):
        raise SubplanError("source must be a native Plan")
    if len(plan.parts) > MAX_SOURCE_PARTS:
        raise SubplanError("source supports at most 4096 parts")
    if isinstance(part_ids, (str, bytes)) or not isinstance(part_ids, Sequence):
        raise SubplanError("part_ids must be a sequence of selected identifiers")
    if not 1 <= len(part_ids) <= MAX_RESULT_PARTS:
        raise SubplanError("select between 1 and 256 part identifiers")
    selected = tuple(part_ids)
    if any(not isinstance(part_id, str) for part_id in selected):
        raise SubplanError("selected part identifiers must be strings")
    if len(selected) != len(set(selected)):
        raise SubplanError("selected part identifiers must be unique")

    # Capture the complete source through native constructor validation before
    # choosing rows. Keep direct-constructor tag repetitions and dependency
    # order, and refuse stale historically admitted mutable Part-like inputs.
    captured = Plan(plan.project_id, tuple(
        Part(part.id, part.instruction, part.depends_on, part.tags)
        for part in plan.parts
    ))
    if captured.digest != plan.digest:
        raise SubplanError("source Plan has changed since validation")
    if project_id == captured.project_id:
        raise SubplanError("new project identifier must differ from the source")
    by_id = {part.id: part for part in captured.parts}
    if any(part_id not in by_id for part_id in selected):
        raise SubplanError("selection contains an unknown part identifier")

    included: set[str] = set()
    pending = list(selected)
    while pending:
        part_id = pending.pop()
        if part_id in included:
            continue
        included.add(part_id)
        if len(included) > MAX_RESULT_PARTS:
            raise SubplanError("dependency closure exceeds the 256-part consumer limit")
        pending.extend(by_id[part_id].depends_on)
    result = Plan(project_id, tuple(
        part for part in captured.parts if part.id in included
    ))
    _serialize(result)
    return result


def _read_plan(path: Path) -> Plan:
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise SubplanError("source must be a regular file")
        if metadata.st_size > MAX_PLAN_BYTES:
            raise SubplanError("source input exceeds the 1 MiB consumer limit")
        content = source.read(MAX_PLAN_BYTES + 1)
    if len(content) > MAX_PLAN_BYTES:
        raise SubplanError("source input exceeds the 1 MiB consumer limit")
    value = strict_json_loads(content.decode("utf-8"))
    if isinstance(value, dict) and isinstance(value.get("parts"), list):
        if len(value["parts"]) > MAX_SOURCE_PARTS:
            raise SubplanError("source supports at most 4096 parts")
    return Plan.from_dict(value)


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
        description="Extract selected authored parts and all prerequisites as a new native Plan.",
        allow_abbrev=False,
    )
    parser.add_argument("--plan", type=Path, required=True, help="complete authored source plan JSON")
    parser.add_argument("--part", action="append", required=True, help="exact selected part ID; repeat for several")
    parser.add_argument("--project", required=True, help="new project ID, different from the source")
    args = parser.parse_args(argv)
    try:
        result = select_subplan(_read_plan(args.plan), args.part, args.project)
        content = _serialize(result)
    except RecursionError:
        print("fanout subplan: input nesting exceeds consumer limits", file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print(f"fanout subplan: cannot produce plan: {exc}", file=sys.stderr)
        return 2
    try:
        _write_stdout(content)
    except OSError as exc:
        print(f"fanout subplan: cannot write plan: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
