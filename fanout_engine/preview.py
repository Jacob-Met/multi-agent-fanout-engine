"""Preview an authored plan and its configured routes without dispatching it."""
from __future__ import annotations

import argparse
from collections.abc import Mapping
import hashlib
import os
from pathlib import Path
import stat
import sys
import tempfile
from typing import Any

from .plan import Plan, canonical_json, strict_json_loads
from .routing import EffortRouter, Route

MAX_PLAN_BYTES = 1024 * 1024
MAX_ROUTING_BYTES = 256 * 1024
MAX_PARTS = 256
MAX_MODELS = 256
MAX_POOL_ROUTES = 256
MAX_REPORT_BYTES = 4 * 1024 * 1024


class PreviewError(ValueError):
    """Raised when a request exceeds the preview consumer's contract."""


def _route_document(route: Route) -> dict[str, str]:
    return {"model": route.model, "effort": route.effort}


def _serialize(report: dict[str, Any]) -> bytes:
    encoded = (canonical_json(report) + "\n").encode("utf-8")
    if len(encoded) > MAX_REPORT_BYTES:
        raise PreviewError("preview report exceeds the 4 MiB consumer limit")
    return encoded


def preview_plan(
    plan: Plan,
    router: EffortRouter,
    *,
    explicit_routes: Mapping[str, Route] | None = None,
) -> dict[str, Any]:
    """Return native plan identity, initial readiness and all configured routes.

    This has no completion evidence or stored dispatch state. The configured
    step-up is reported as metadata; it is never performed by this consumer.
    """
    if not isinstance(plan, Plan) or not isinstance(router, EffortRouter):
        raise PreviewError("preview requires a native Plan and EffortRouter")
    if len(plan.parts) > MAX_PARTS:
        raise PreviewError("preview supports at most 256 parts")
    if explicit_routes is None:
        explicit_routes = {}
    if not isinstance(explicit_routes, Mapping):
        raise PreviewError("explicit_routes must map part identifiers to Routes")
    explicit = dict(explicit_routes)
    known = {part.id for part in plan.parts}
    if any(not isinstance(key, str) or key not in known for key in explicit):
        raise PreviewError("explicit_routes contains an unknown part identifier")
    if any(not isinstance(value, Route) for value in explicit.values()):
        raise PreviewError("every explicit route must be a native Route")

    routes = []
    for part in plan.parts:
        route = router.route_for(part.id, explicit.get(part.id))
        routes.append({
            "part_id": part.id,
            "route": _route_document(route),
            "route_source": "explicit" if part.id in explicit else "pool",
            "idempotency_key": plan.idempotency_key(part.id),
        })
    report = {
        "schema_version": 1,
        "plan": plan.to_dict(),
        "plan_digest": plan.digest,
        "dependency_ready_without_completions": [
            part.id for part in plan.ready_parts(())
        ],
        "routes": routes,
        "configured_step_up": (
            _route_document(router.step_up) if router.step_up is not None else None
        ),
    }
    _serialize(report)
    return report


def _read_input(path: Path, limit: int, label: str) -> bytes:
    # O_NONBLOCK prevents a named pipe from blocking before the regular-file
    # check on systems that provide it. O_BINARY preserves Windows input bytes.
    flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as source:
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise PreviewError(f"{label} input must be a regular file")
        if metadata.st_size > limit:
            raise PreviewError(f"{label} input exceeds its {limit}-byte consumer limit")
        captured = source.read(limit + 1)
    if len(captured) > limit:
        raise PreviewError(f"{label} input exceeds its {limit}-byte consumer limit")
    return captured


def _read_route(value: Any) -> Route:
    if not isinstance(value, dict) or set(value) != {"model", "effort"}:
        raise PreviewError("each route must contain exactly model and effort")
    if not isinstance(value["model"], str) or not isinstance(value["effort"], str):
        raise PreviewError("route model and effort must be strings")
    return Route(value["model"], value["effort"])


def _read_routing(value: Any) -> tuple[EffortRouter, dict[str, Route]]:
    required = {"catalog", "pool"}
    allowed = required | {"explicit_routes", "step_up"}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - allowed:
        raise PreviewError("routing must contain catalog, pool and only supported optional fields")
    catalog = value["catalog"]
    if not isinstance(catalog, dict) or not catalog or len(catalog) > MAX_MODELS:
        raise PreviewError("catalog must contain between 1 and 256 models")
    for model, efforts in catalog.items():
        if not isinstance(efforts, list) or not efforts:
            raise PreviewError("each catalog model needs a nonempty list of effort strings")
        for effort in efforts:
            if not isinstance(effort, str):
                raise PreviewError("catalog efforts must be strings")
            Route(model, effort)
    pool = value["pool"]
    if not isinstance(pool, list) or not 1 <= len(pool) <= MAX_POOL_ROUTES:
        raise PreviewError("pool must contain between 1 and 256 routes")
    explicit = value.get("explicit_routes", {})
    if not isinstance(explicit, dict):
        raise PreviewError("explicit_routes must be an object")
    overrides = {part_id: _read_route(route) for part_id, route in explicit.items()}
    step_up = value.get("step_up")
    router = EffortRouter(
        catalog,
        pool=tuple(_read_route(route) for route in pool),
        step_up=_read_route(step_up) if step_up is not None else None,
    )
    return router, overrides


def _preview_files(plan_path: Path, routing_path: Path) -> bytes:
    plan_bytes = _read_input(plan_path, MAX_PLAN_BYTES, "plan")
    routing_bytes = _read_input(routing_path, MAX_ROUTING_BYTES, "routing")
    plan_document = strict_json_loads(plan_bytes.decode("utf-8"))
    if isinstance(plan_document, dict) and isinstance(plan_document.get("parts"), list):
        if len(plan_document["parts"]) > MAX_PARTS:
            raise PreviewError("preview supports at most 256 parts")
    plan = Plan.from_dict(plan_document)
    router, explicit = _read_routing(strict_json_loads(routing_bytes.decode("utf-8")))
    report = preview_plan(plan, router, explicit_routes=explicit)
    report["input_sha256"] = {
        "plan": hashlib.sha256(plan_bytes).hexdigest(),
        "routes": hashlib.sha256(routing_bytes).hexdigest(),
    }
    return _serialize(report)


def _publish_new_file(destination: Path, content: bytes) -> None:
    if os.path.lexists(destination):
        raise PreviewError("output already exists; choose a new file")
    fd, temporary = tempfile.mkstemp(prefix=".fanout-preview-", dir=destination.parent)
    published = False
    try:
        with os.fdopen(fd, "wb") as stage:
            stage.write(content)
            stage.flush()
            os.fsync(stage.fileno())
        os.link(temporary, destination)
        published = True
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        except OSError as exc:
            if published:
                raise PreviewError("preview was published but staging cleanup failed") from exc
            raise


def _write_stdout(content: bytes) -> None:
    try:
        sys.stdout.buffer.write(content)
        sys.stdout.buffer.flush()
    except OSError:
        # Prevent a second buffered flush from masking the clean CLI refusal at
        # interpreter shutdown. A stream may already have received a prefix.
        try:
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview an authored plan and its routes without opening a Ledger or dispatching work.",
        allow_abbrev=False,
    )
    parser.add_argument("--plan", type=Path, required=True, help="authored plan JSON file")
    parser.add_argument("--routes", type=Path, required=True, help="caller-supplied routing JSON file")
    parser.add_argument("--output", type=Path, help="new report file; otherwise write JSON to stdout")
    args = parser.parse_args(argv)
    try:
        content = _preview_files(args.plan, args.routes)
        if args.output is None:
            _write_stdout(content)
        else:
            _publish_new_file(args.output, content)
    except RecursionError:
        print("fanout preview: input nesting exceeds preview limits", file=sys.stderr)
        return 2
    except (ValueError, OSError) as exc:
        print(f"fanout preview: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
