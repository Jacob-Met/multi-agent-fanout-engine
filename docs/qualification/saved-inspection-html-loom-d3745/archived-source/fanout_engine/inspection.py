"""Read-only inspection of a project already recorded in the native ledger."""
from __future__ import annotations

import math
from typing import Any

from .ledger import Ledger, LedgerError, _STATES
from .plan import Part, Plan, PlanError, canonical_json, strict_json_loads


class InspectionError(LedgerError):
    """A missing project or inconsistent recorded data prevented inspection."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _invalid(message: str) -> InspectionError:
    return InspectionError("invalid_record", message)


def _decode(value: Any, label: str, *, nullable: bool = False) -> Any:
    if value is None and nullable:
        return None
    if not isinstance(value, str):
        raise _invalid(f"{label} is not stored JSON text")
    try:
        result = strict_json_loads(value)
        canonical_json(result).encode("utf-8")
        return result
    except (ValueError, RecursionError) as exc:
        raise _invalid(f"{label} cannot be decoded as finite UTF-8 JSON") from exc


def _read_plan(snapshot: dict[str, Any]) -> Plan:
    document = _decode(snapshot["plan_json"], "plan")
    try:
        checked = Plan.from_dict(document)
        # from_dict normalizes tags; direct Plan/Part construction need not.
        # Keep the exact native representation which record_plan persisted.
        parts = tuple(
            Part(part.id, part.instruction, part.depends_on,
                 tuple(raw.get("tags", [])))
            for part, raw in zip(checked.parts, document["parts"])
        )
        plan = Plan(checked.project_id, parts)
        if canonical_json(document) != canonical_json(plan.to_dict()):
            raise _invalid("stored plan does not match its native representation")
    except (PlanError, UnicodeError, RecursionError) as exc:
        raise _invalid("stored plan is malformed") from exc
    if plan.project_id != snapshot["project_id"] or plan.digest != snapshot["plan_digest"]:
        raise _invalid("stored plan identity does not match its recorded digest")
    return plan


def inspect_project(ledger: Ledger, project_id: str) -> dict[str, Any]:
    """Describe one recorded project without dispatching or changing its state.

    queued_ready_ids is the observed intersection of queued state and completed
    direct prerequisites. It is not a dispatch reservation, a route/worker check,
    or a conclusion about external work. Native uncertainty stays uncertainty.
    """
    snapshot = ledger.project_snapshot(project_id)
    if snapshot is None:
        raise InspectionError("project_not_found", "project is not in the ledger")
    plan = _read_plan(snapshot)
    rows: dict[str, dict[str, Any]] = {}
    expected = {part.id for part in plan.parts}
    for row in snapshot["parts"]:
        part_id = row["part_id"]
        if not isinstance(part_id, str) or part_id in rows or part_id not in expected:
            raise _invalid("stored parts contain an unexpected or repeated identifier")
        rows[part_id] = row
    missing = [part.id for part in plan.parts if part.id not in rows]
    if missing:
        raise InspectionError("missing_parts", "stored project is missing parts: " + ", ".join(missing))

    # Validate the complete snapshot before returning any partial report.
    decoded: dict[str, dict[str, Any]] = {}
    for part in plan.parts:
        row = rows[part.id]
        payload = _decode(row["payload_json"], f"part {part.id} payload")
        if (row["project_id"] != plan.project_id
                or row["payload_digest"] != plan.digest
                or row["idempotency_key"] != plan.idempotency_key(part.id)
                or canonical_json(payload) != canonical_json(part.to_dict())):
            raise _invalid(f"part {part.id} does not match its recorded plan")
        if row["state"] not in _STATES:
            raise _invalid(f"part {part.id} has an unknown stored state")
        if any(row[name] is not None and not isinstance(row[name], str)
               for name in ("worker_id", "task_id", "artifact_ref")):
            raise _invalid(f"part {part.id} has a malformed native reference")
        if (not isinstance(row["updated_at"], (int, float))
                or not math.isfinite(row["updated_at"])):
            raise _invalid(f"part {part.id} has a malformed update timestamp")
        decoded[part.id] = {
            "route": _decode(row["route_json"], f"part {part.id} route", nullable=True),
            "evidence": _decode(row["evidence_json"], f"part {part.id} evidence", nullable=True),
        }

    counts = {state: 0 for state in sorted(_STATES)}
    parts: list[dict[str, Any]] = []
    ready: list[str] = []
    blocked: list[str] = []
    for part in plan.parts:
        row = rows[part.id]
        state = row["state"]
        unmet = [{"id": dependency, "state": rows[dependency]["state"]}
                 for dependency in part.depends_on
                 if rows[dependency]["state"] != "completed"]
        counts[state] += 1
        if state == "queued":
            (blocked if unmet else ready).append(part.id)
        parts.append({
            **part.to_dict(),
            "state": state,
            "idempotency_key": row["idempotency_key"],
            "worker_id": row["worker_id"],
            "task_id": row["task_id"],
            "route": decoded[part.id]["route"],
            "artifact_ref": row["artifact_ref"],
            "evidence": decoded[part.id]["evidence"],
            "updated_at": row["updated_at"],
            "unmet_dependencies": unmet,
        })
    report = {
        "project_id": plan.project_id,
        "plan_digest": plan.digest,
        "state_counts": counts,
        "queued_ready_ids": ready,
        "blocked_queued_ids": blocked,
        "parts": parts,
    }
    try:
        canonical_json(report).encode("utf-8")
    except (PlanError, UnicodeError, RecursionError) as exc:
        raise _invalid("stored part values cannot form a finite UTF-8 JSON report") from exc
    return report
