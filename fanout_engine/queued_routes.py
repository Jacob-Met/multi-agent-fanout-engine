"""Preview configured routes for queued-ready parts in a retained ledger."""
from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
from pathlib import Path
import sqlite3
import sys
from typing import Any

from .inspection import InspectionError, inspect_project
from .ledger import Ledger, LedgerError
from .plan import canonical_json, strict_json_loads
from .preview import (
    MAX_PARTS, MAX_POOL_ROUTES, MAX_REPORT_BYTES, MAX_ROUTING_BYTES,
    PreviewError, _read_input, _read_routing, _write_stdout,
)
from .routing import EffortRouter, Route


def _serialize(report: dict[str, Any]) -> bytes:
    content = (canonical_json(report) + "\n").encode("utf-8")
    if len(content) > MAX_REPORT_BYTES:
        raise PreviewError("queued-route report exceeds the 4 MiB consumer limit")
    return content


def queued_route_report(
    ledger: Ledger,
    project_id: str,
    router: EffortRouter,
    *,
    explicit_routes: Mapping[str, Route] | None = None,
) -> dict[str, Any]:
    """Return advisory routes from one validated retained-project snapshot.

    No dispatch reservation, worker availability or external outcome is inferred.
    All supplied overrides are validated even when their parts are not ready.
    The caller retains ownership of its connection and any active transaction.
    """
    if not isinstance(router, EffortRouter):
        raise PreviewError("queued-route preview requires a native EffortRouter")
    snapshot = inspect_project(ledger, project_id)
    if len(snapshot["parts"]) > MAX_PARTS:
        raise PreviewError("queued-route preview supports at most 256 parts")
    if explicit_routes is None:
        explicit_routes = {}
    if not isinstance(explicit_routes, Mapping):
        raise PreviewError("explicit_routes must map part identifiers to Routes")
    explicit = dict(explicit_routes)
    known = {part["id"] for part in snapshot["parts"]}
    if any(not isinstance(key, str) or key not in known for key in explicit):
        raise PreviewError("explicit_routes contains an unknown part identifier")

    # Validate whole configuration, including the empty-ready case. This
    # preview deliberately does not copy dispatch's selected-only timing.
    pool = tuple(router.pool)
    if not 1 <= len(pool) <= MAX_POOL_ROUTES:
        raise PreviewError("pool must contain between 1 and 256 routes")
    step_up = router.step_up
    for route in (*pool, *explicit.values(), *((step_up,) if step_up is not None else ())):
        if not isinstance(route, Route):
            raise PreviewError("configured routes must be native Routes")
        router._validate(route)

    ready = set(snapshot["queued_ready_ids"])
    selected = []
    for part in snapshot["parts"]:
        if part["id"] not in ready:
            continue
        route = router.route_for(part["id"], explicit.get(part["id"]))
        selected.append({
            "part_id": part["id"],
            "route": {"model": route.model, "effort": route.effort},
            "route_source": "explicit" if part["id"] in explicit else "pool",
            "idempotency_key": part["idempotency_key"],
        })
    report = {
        "schema_version": 1,
        "project_id": snapshot["project_id"],
        "plan_digest": snapshot["plan_digest"],
        "state_counts": snapshot["state_counts"],
        "queued_ready_ids": snapshot["queued_ready_ids"],
        "blocked_queued_ids": snapshot["blocked_queued_ids"],
        "parts": [
            {"id": part["id"], "state": part["state"],
             "unmet_dependencies": part["unmet_dependencies"]}
            for part in snapshot["parts"]
        ],
        "routes": selected,
        "configured_step_up": (
            {"model": step_up.model, "effort": step_up.effort}
            if step_up is not None else None
        ),
    }
    _serialize(report)
    return report


class _Once(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if hasattr(namespace, self.dest):
            parser.error(f"{option_string} may be supplied only once")
        setattr(namespace, self.dest, values)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview advisory routes for currently queued-ready retained parts; no dispatch.",
        allow_abbrev=False,
    )
    parser.add_argument("--database", type=Path, required=True, action=_Once,
                        default=argparse.SUPPRESS, help="existing SQLite ledger file")
    parser.add_argument("--project", required=True, action=_Once,
                        default=argparse.SUPPRESS, help="exact retained project identifier")
    parser.add_argument("--routes", type=Path, required=True, action=_Once,
                        default=argparse.SUPPRESS, help="caller-supplied routing JSON file")
    args = parser.parse_args(argv)
    try:
        captured = _read_input(args.routes, MAX_ROUTING_BYTES, "routing")
        router, explicit = _read_routing(strict_json_loads(captured.decode("utf-8")))
        with Ledger.open_readonly(args.database) as ledger:
            report = queued_route_report(
                ledger, args.project, router, explicit_routes=explicit,
            )
        report["routing_input_sha256"] = hashlib.sha256(captured).hexdigest()
        content = _serialize(report)
    except InspectionError as exc:
        print(f"fanout queued routes: {exc.code}: {exc}", file=sys.stderr)
        return 3 if exc.code == "project_not_found" else 2
    except RecursionError:
        print("fanout queued routes: input nesting exceeds consumer limits", file=sys.stderr)
        return 2
    except (LedgerError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"fanout queued routes: cannot preview retained routes: {exc}", file=sys.stderr)
        return 2
    try:
        if sys.stdout is None:
            raise OSError("standard output is unavailable")
        _write_stdout(content)
    except OSError as exc:
        print(f"fanout queued routes: cannot write report: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
