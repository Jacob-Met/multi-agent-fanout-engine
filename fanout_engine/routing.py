"""Deterministic effort-aware route selection with guarded step-up."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Iterable, Mapping

_EFFORTS = {"low", "medium", "high", "xhigh", "max"}
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


class UnsafeStepUp(RuntimeError):
    """Raised when fallback would risk duplicating output or a side effect."""


@dataclass(frozen=True)
class Route:
    model: str
    effort: str

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not _MODEL.fullmatch(self.model):
            raise ValueError("invalid model identifier")
        if self.effort not in _EFFORTS:
            raise ValueError("unsupported reasoning effort")


class EffortRouter:
    """Route parts only within a caller-supplied authorized model catalog."""

    def __init__(
        self,
        authorized_catalog: Mapping[str, Iterable[str]],
        *,
        pool: Iterable[Route],
        step_up: Route | None = None,
    ) -> None:
        self._catalog = {name: frozenset(levels) for name, levels in authorized_catalog.items()}
        self.pool = tuple(pool)
        self.step_up = step_up
        if not self.pool:
            raise ValueError("route pool cannot be empty")
        for route in (*self.pool, *((step_up,) if step_up else ())):
            self._validate(route)

    def _validate(self, route: Route) -> None:
        if route.model not in self._catalog:
            raise ValueError("route is not in the authorized catalog")
        if route.effort not in self._catalog[route.model]:
            raise ValueError("effort is not authorized for this model")

    def route_for(self, part_id: str, explicit: Route | None = None) -> Route:
        if explicit is not None:
            self._validate(explicit)
            return explicit
        digest = hashlib.sha256(part_id.encode("utf-8")).digest()
        index = int.from_bytes(digest[:8], "big") % len(self.pool)
        return self.pool[index]

    def step_up_after_refusal(
        self,
        current: Route,
        *,
        refusal_before_output: bool,
        output_received: bool = False,
        effect_started: bool = False,
    ) -> Route:
        if not refusal_before_output or output_received or effect_started:
            raise UnsafeStepUp("step-up is unsafe after output or an effect")
        if self.step_up is None or self.step_up == current:
            raise UnsafeStepUp("no distinct authorized step-up route is configured")
        self._validate(self.step_up)
        return self.step_up
