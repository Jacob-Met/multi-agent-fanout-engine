"""Plan validation and deterministic identity helpers."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
import hashlib
import json
import math
import re
from typing import Any, Iterable

_IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9._-]{0,63}\Z")


class PlanError(ValueError):
    """Raised when a plan is malformed or internally inconsistent."""


def canonical_json(value: Any) -> str:
    """Serialize JSON deterministically and reject non-JSON numeric values."""
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise PlanError("value is not canonical JSON") from exc


def strict_json_loads(text: str) -> Any:
    """Parse JSON while rejecting duplicate object keys and non-finite numbers."""
    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise PlanError("duplicate JSON object key")
            result[key] = value
        return result

    def invalid_constant(_: str) -> Any:
        raise PlanError("non-finite JSON number")

    def finite_float(value: str) -> float:
        number = float(value)
        if not math.isfinite(number):
            raise PlanError("non-finite JSON number")
        return number

    try:
        return json.loads(
            text, object_pairs_hook=object_pairs,
            parse_constant=invalid_constant, parse_float=finite_float,
        )
    except PlanError:
        raise
    except (TypeError, json.JSONDecodeError) as exc:
        raise PlanError("invalid JSON document") from exc


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise PlanError(f"invalid {label}")
    return value


@dataclass(frozen=True)
class Part:
    id: str
    instruction: str
    depends_on: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "depends_on", tuple(self.depends_on))
        object.__setattr__(self, "tags", tuple(self.tags))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "instruction": self.instruction,
            "depends_on": list(self.depends_on),
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class Plan:
    project_id: str
    parts: tuple[Part, ...]
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parts", tuple(self.parts))
        _identifier(self.project_id, "project identifier")
        if not self.parts:
            raise PlanError("a plan must contain at least one part")
        ids = [part.id for part in self.parts]
        if len(ids) != len(set(ids)):
            raise PlanError("part identifiers must be unique")
        known = set(ids)
        for part in self.parts:
            _identifier(part.id, "part identifier")
            if not isinstance(part.instruction, str) or not part.instruction.strip():
                raise PlanError("each part needs a non-empty instruction")
            if len(part.depends_on) != len(set(part.depends_on)):
                raise PlanError("dependencies must be unique")
            if part.id in part.depends_on:
                raise PlanError("a part cannot depend on itself")
            if not set(part.depends_on) <= known:
                raise PlanError("a dependency references an unknown part")
            for tag in part.tags:
                _identifier(tag, "tag")
        self._check_acyclic()
        try:
            encoded = canonical_json(self.to_dict()).encode("utf-8")
        except UnicodeEncodeError as exc:
            raise PlanError("plan contains text that is not valid UTF-8") from exc
        object.__setattr__(self, "digest", hashlib.sha256(encoded).hexdigest())

    @classmethod
    def from_dict(cls, value: Any) -> "Plan":
        if not isinstance(value, dict) or set(value) != {"project", "parts"}:
            raise PlanError("plan must contain exactly project and parts")
        project = _identifier(value["project"], "project identifier")
        raw_parts = value["parts"]
        if not isinstance(raw_parts, list):
            raise PlanError("parts must be a list")
        parts: list[Part] = []
        for item in raw_parts:
            if not isinstance(item, dict):
                raise PlanError("each part must be an object")
            allowed = {"id", "instruction", "depends_on", "tags"}
            if set(item) - allowed or not {"id", "instruction"} <= set(item):
                raise PlanError("part has missing or unexpected fields")
            part_id = _identifier(item["id"], "part identifier")
            deps = item.get("depends_on", [])
            tags = item.get("tags", [])
            if not isinstance(deps, list) or not all(isinstance(x, str) for x in deps):
                raise PlanError("depends_on must be a list of identifiers")
            if not isinstance(tags, list) or not all(isinstance(x, str) for x in tags):
                raise PlanError("tags must be a list of identifiers")
            parts.append(Part(part_id, item["instruction"], tuple(deps), tuple(sorted(set(tags)))))
        return cls(project, tuple(parts))

    def to_dict(self) -> dict[str, Any]:
        return {"project": self.project_id, "parts": [part.to_dict() for part in self.parts]}

    def _check_acyclic(self) -> None:
        remaining = {part.id: len(part.depends_on) for part in self.parts}
        dependents: dict[str, list[str]] = {part.id: [] for part in self.parts}
        for part in self.parts:
            for parent in part.depends_on:
                dependents[parent].append(part.id)
        ready = [part_id for part_id, count in remaining.items() if count == 0]
        visited = 0
        # Walk the graph without consuming Python stack frames for each edge.
        # This validation does not reorder the authored parts or dependencies.
        while ready:
            part_id = ready.pop()
            visited += 1
            for dependent in dependents[part_id]:
                remaining[dependent] -= 1
                if remaining[dependent] == 0:
                    ready.append(dependent)
        if visited != len(self.parts):
            raise PlanError("dependency graph contains a cycle")

    def ready_parts(self, completed: Iterable[str] = ()) -> tuple[Part, ...]:
        done = set(completed)
        return tuple(part for part in self.parts if set(part.depends_on) <= done)

    def idempotency_key(self, part_id: str) -> str:
        _identifier(part_id, "part identifier")
        part_ids = self._part_ids
        if part_ids is None:
            # Keep live membership for historically accepted mutable Part-like
            # objects. Only the native immutable shape is cached.
            part_ids = {part.id for part in self.parts}
        if part_id not in part_ids:
            raise PlanError("unknown part identifier")
        material = f"{self.project_id}\0{self.digest}\0{part_id}".encode("utf-8")
        return "fanout-" + hashlib.sha256(material).hexdigest()

    @cached_property
    def _part_ids(self) -> frozenset[str] | None:
        if type(self.parts) is not tuple or any(
            type(part) is not Part or type(part.id) is not str for part in self.parts
        ):
            return None
        return frozenset(part.id for part in self.parts)
