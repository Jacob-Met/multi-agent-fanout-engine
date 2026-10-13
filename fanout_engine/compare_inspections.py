"""Describe literal differences between two saved inspection documents."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys
from typing import Any

from .plan import canonical_json, strict_json_loads
from .preview import _publish_new_file, _read_input, _write_stdout

MAX_INPUT_BYTES = 1024 * 1024
MAX_PARTS = 256
MAX_REPORT_BYTES = 8 * 1024 * 1024


class InspectionComparisonError(ValueError):
    """The saved documents cannot form a complete descriptive comparison."""


def _admit(raw: bytes, label: str) -> dict[str, Any]:
    if not isinstance(raw, bytes):
        raise InspectionComparisonError(f"{label} must be raw bytes")
    if len(raw) > MAX_INPUT_BYTES:
        raise InspectionComparisonError(f"{label} exceeds the 1 MiB input limit")
    try:
        document = strict_json_loads(raw.decode("utf-8"))
        canonical_json(document).encode("utf-8")
    except ValueError as exc:
        raise InspectionComparisonError(f"{label} must contain finite UTF-8 JSON") from exc
    if not isinstance(document, dict):
        raise InspectionComparisonError(f"{label} must contain an object")
    for field in ("project_id", "plan_digest"):
        value = document.get(field)
        if not isinstance(value, str) or not value:
            raise InspectionComparisonError(f"{label} needs a nonempty string {field}")
    parts = document.get("parts")
    if not isinstance(parts, list) or len(parts) > MAX_PARTS:
        raise InspectionComparisonError(f"{label} needs an array of at most 256 parts")
    seen: set[str] = set()
    for part in parts:
        if not isinstance(part, dict):
            raise InspectionComparisonError(f"{label} parts must be objects")
        part_id = part.get("id")
        if not isinstance(part_id, str) or not part_id or part_id in seen:
            raise InspectionComparisonError(f"{label} needs unique nonempty string part IDs")
        seen.add(part_id)
    return document


def _side(document: dict[str, Any], field: str) -> dict[str, Any]:
    if field not in document:
        return {"present": False}
    return {"present": True, "value": document[field]}


def _field_changes(
    first: dict[str, Any], second: dict[str, Any], excluded: set[str],
) -> list[dict[str, Any]]:
    changes = []
    for field in sorted((set(first) | set(second)) - excluded):
        left, right = _side(first, field), _side(second, field)
        # Python equality aliases True/1/1.0 and signed zero. The native JSON
        # representation keeps the distinctions available after parsing.
        if canonical_json(left) != canonical_json(right):
            changes.append({"field": field, "first": left, "second": right})
    return changes


def _serialize(report: dict[str, Any]) -> bytes:
    content = (canonical_json(report) + "\n").encode("utf-8")
    if len(content) > MAX_REPORT_BYTES:
        raise InspectionComparisonError("comparison exceeds the 8 MiB report limit")
    return content


def compare_inspections(first: bytes, second: bytes) -> dict[str, Any]:
    """Compare saved values for the same declared project, plan and part set.

    This checks document shape and declared relationships only. It does not
    validate a native plan, authenticate an observation, establish chronology,
    resolve uncertainty or authorize any work. Inputs are caller-owned bytes;
    complete parsed documents and their raw identities remain in the result.
    """
    left, right = _admit(first, "first"), _admit(second, "second")
    for field in ("project_id", "plan_digest"):
        if left[field] != right[field]:
            raise InspectionComparisonError(f"documents must have the same {field}")
    left_parts = {part["id"]: part for part in left["parts"]}
    right_parts = {part["id"]: part for part in right["parts"]}
    if set(left_parts) != set(right_parts):
        raise InspectionComparisonError("documents must have the same complete part-ID set")
    part_changes = []
    for part_id, part in left_parts.items():
        fields = _field_changes(part, right_parts[part_id], {"id"})
        if fields:
            part_changes.append({"part_id": part_id, "fields": fields})
    report = {
        "schema": "fanout.saved-inspection-comparison/1",
        "saved_data_only": True,
        "first": {"input_bytes": len(first),
                  "input_sha256": hashlib.sha256(first).hexdigest(), "document": left},
        "second": {"input_bytes": len(second),
                   "input_sha256": hashlib.sha256(second).hexdigest(), "document": right},
        "same_input_bytes": first == second,
        "same_saved_values": canonical_json(left) == canonical_json(right),
        "part_order_changed": list(left_parts) != list(right_parts),
        "top_level_changes": _field_changes(left, right, {"parts"}),
        "changed_part_ids": [row["part_id"] for row in part_changes],
        "part_changes": part_changes,
    }
    _serialize(report)
    return report


def _parser() -> argparse.ArgumentParser:
    options: dict[str, Any] = {}
    if sys.version_info >= (3, 14):
        # This JSON-oriented reader uses plain help/errors, including when an
        # imported caller lends it an unavailable or descriptor-free stdout.
        options["color"] = False
        options["formatter_class"] = lambda prog: argparse.HelpFormatter(prog, color=False)
    parser = argparse.ArgumentParser(
        description="Compare two saved inspection JSON documents without opening a Ledger or rerunning work.",
        allow_abbrev=False, **options,
    )
    parser.add_argument("--first", type=Path, required=True, help="first saved inspection JSON file")
    parser.add_argument("--second", type=Path, required=True, help="second saved inspection JSON file")
    parser.add_argument("--output", type=Path, help="new comparison file; otherwise write JSON to stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        first = _read_input(args.first, MAX_INPUT_BYTES, "first")
        second = _read_input(args.second, MAX_INPUT_BYTES, "second")
        content = _serialize(compare_inspections(first, second))
    except RecursionError:
        print("fanout compare-inspections: input nesting exceeds comparison limits", file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print(f"fanout compare-inspections: cannot compare saved documents: {exc}", file=sys.stderr)
        return 2
    try:
        if args.output is None:
            _write_stdout(content)
        else:
            _publish_new_file(args.output, content)
    except (ValueError, OSError) as exc:
        print(f"fanout compare-inspections: cannot write report: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
