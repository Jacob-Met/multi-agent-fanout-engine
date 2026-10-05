# Multi-agent Fan-out Engine

A small, sanitized Python reference implementation for splitting a project into independent parts, tracking each dispatch in a SQLite ledger, and routing work by requested reasoning effort.

> **AI-assisted:** The code and documentation were developed iteratively with AI assistance, then manually reviewed and exercised with the tests and local demo in this repository.

This is a public-safe reference edition derived from a larger Python fan-out system. Deployment adapters, account identities, private endpoints, host policy, and operator-specific prompts are intentionally excluded. The package does not call a model provider or remote worker service; callers supply an authorized route catalog and a `Hub` adapter.

## What it demonstrates

- **Fan-out parts:** a validated dependency graph makes ready parts explicit; downstream work stays queued until its prerequisites complete.
- **Dispatch ledger:** SQLite records a stable idempotency key, selected route, task reference, state changes, and reconciliation evidence.
- **Reconcile, never replay:** an ambiguous submit is parked as `outcome_unknown`. The dispatcher will not submit it again. Resolve it only after reading external evidence and recording a finding.
- **Effort routing:** a stable per-part choice selects from a caller-supplied pool. An explicit route wins. A step-up route is permitted only for a refusal before any output or side effect.
- **Adapter boundary:** the `Hub` protocol keeps transport and authentication outside the reference core.

## Run

Requires Python 3.10+ and the standard library only.

```sh
python -m unittest discover -s tests -v
python examples/demo.py
```

The tests use an in-memory SQLite ledger and a local fake adapter. The demo is also local. **No production worker capacity, external dispatch volume, or benchmark scale is claimed by this repository.**

## Minimal integration shape

```python
from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready

catalog = {"model-a": ("low", "high"), "model-b": ("low", "high")}
router = EffortRouter(
    catalog,
    pool=(Route("model-a", "low"), Route("model-b", "low")),
    step_up=Route("model-b", "high"),
)
plan = Plan.from_dict({
    "project": "sample",
    "parts": [
        {"id": "research", "instruction": "Collect source material."},
        {"id": "draft", "instruction": "Write a draft.", "depends_on": ["research"]},
    ],
})

with Ledger(":memory:") as ledger:
    report = dispatch_ready(plan, ledger, hub, router, worker_for=lambda part: "worker-a")
```

`hub` must implement `submit(part, *, route, worker_id, idempotency_key)` and return a non-empty `task_id` after acceptance. If it cannot prove whether a request was accepted, raise an exception: the part is recorded as unknown and is not submitted again.

## Scope

This is a reference core, not a turnkey agent, scheduler, or deployment package. It contains no credentials, provider-specific model list, private routing policy, or live service endpoint. An integration should enforce its own authorization, rate limits, storage policy, and evidence requirements before connecting an adapter.
