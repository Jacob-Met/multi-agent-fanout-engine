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
    ledger.record_plan(plan)
    completed = ledger.completed_ids(plan.project_id)
    ready = {part.id for part in plan.ready_parts(completed)}
    started: list[str] = []
    unknown: list[str] = []
    not_ready: list[str] = []
    explicit_routes = explicit_routes or {}

    for part in plan.parts:
        if part.id not in ready:
            if ledger.part_state(plan.project_id, part.id) == "queued":
                not_ready.append(part.id)
            continue
        if part.id not in ledger.dispatchable_ids(plan.project_id):
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
        task_id = response.get("task_id") if isinstance(response, Mapping) else None
        if not isinstance(task_id, str) or not task_id.strip():
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
