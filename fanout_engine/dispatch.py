"""Adapter-driven dispatch of dependency-ready parts."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Protocol

from .ledger import Ledger, LedgerError
from .plan import Part, Plan
from .routing import EffortRouter, Route


class Hub(Protocol):
    def submit(self, part: Part, *, route: Route, worker_id: str,
               idempotency_key: str) -> Mapping[str, str]:
        """Submit one part using the stable key and return a task_id after acceptance."""


@dataclass(frozen=True)
class DispatchReport:
    started: tuple[str, ...]
    outcome_unknown: tuple[str, ...]
    not_ready: tuple[str, ...]


def dispatch_ready(
    plan: Plan,
    ledger: Ledger,
    hub: Hub,
    router: EffortRouter,
    *,
    worker_for: Callable[[Part], str],
    explicit_routes: Mapping[str, Route] | None = None,
) -> DispatchReport:
    """Submit queued, dependency-ready parts once; ambiguous submits are parked."""
    if type(plan) is Plan and any(type(part) is not Part for part in plan.parts):
        # Native Plan/Part values are frozen and keep their existing object
        # identity. Capture historically admitted mutable Part-like sources
        # before callbacks can change payloads independently of recorded keys.
        captured = Plan(plan.project_id, tuple(
            part if type(part) is Part else
            Part(part.id, part.instruction, part.depends_on, part.tags)
            for part in plan.parts
        ))
        if captured.digest != plan.digest:
            raise LedgerError("plan has changed since validation")
        plan = captured
    if explicit_routes is None:
        explicit_routes = {}
    if not isinstance(explicit_routes, Mapping):
        raise ValueError("explicit_routes must map part identifiers to Routes")
    explicit_routes = dict(explicit_routes)
    known = {part.id for part in plan.parts}
    if any(not isinstance(key, str) or key not in known for key in explicit_routes):
        raise ValueError("explicit_routes contains an unknown part identifier")
    if any(not isinstance(route, Route) for route in explicit_routes.values()):
        raise ValueError("every explicit route must be a native Route")

    ledger.record_plan(plan)
    completed = ledger.completed_ids(plan.project_id)
    ready = {part.id for part in plan.ready_parts(completed)}
    started: list[str] = []
    unknown: list[str] = []
    not_ready: list[str] = []
    for part in plan.parts:
        if part.id not in ready:
            if ledger.part_state(plan.project_id, part.id) == "queued":
                not_ready.append(part.id)
            continue
        if ledger.part_state(plan.project_id, part.id) != "queued":
            continue
        worker_id = worker_for(part)
        route = router.route_for(part.id, explicit_routes.get(part.id))
        key = ledger.idempotency_key(plan.project_id, part.id)
        ledger.mark_dispatching(plan.project_id, part.id, worker_id,
                                {"model": route.model, "effort": route.effort})
        try:
            response = hub.submit(part, route=route, worker_id=worker_id, idempotency_key=key)
        except Exception as exc:
            ledger.mark_outcome_unknown(
                plan.project_id, part.id,
                {"source": "hub adapter", "locator": key,
                 "finding": f"submit raised {type(exc).__name__}; remote acceptance is unverified"},
            )
            unknown.append(part.id)
            continue
        try:
            task_id = response.get("task_id") if isinstance(response, Mapping) else None
            valid_task_id = isinstance(task_id, str) and bool(task_id.strip())
            if valid_task_id:
                try:
                    str.encode(task_id, "utf-8")
                except UnicodeEncodeError:
                    # An identifier SQLite cannot retain is not a usable receipt.
                    valid_task_id = False
        except Exception as exc:
            ledger.mark_outcome_unknown(
                plan.project_id, part.id,
                {"source": "hub adapter", "locator": key,
                 "finding": f"submit response raised {type(exc).__name__}; remote acceptance is unverified"},
            )
            unknown.append(part.id)
            continue
        if not valid_task_id:
            ledger.mark_outcome_unknown(
                plan.project_id, part.id,
                {"source": "hub adapter", "locator": key,
                 "finding": "submit returned no verifiable task identifier"},
            )
            unknown.append(part.id)
            continue
        try:
            ledger.mark_running(plan.project_id, part.id, task_id)
        except LedgerError:
            # The adapter may have accepted work even if our local acknowledgement failed.
            ledger.mark_outcome_unknown(
                plan.project_id, part.id,
                {"source": "ledger", "locator": key,
                 "finding": "remote acceptance was returned but local state could not be advanced"},
            )
            unknown.append(part.id)
            continue
        started.append(part.id)
    return DispatchReport(tuple(started), tuple(unknown), tuple(not_ready))
