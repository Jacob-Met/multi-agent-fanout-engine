# Multi-agent Fan-out Engine

[![test](https://github.com/Jacob-Met/multi-agent-fanout-engine/actions/workflows/test.yml/badge.svg)](https://github.com/Jacob-Met/multi-agent-fanout-engine/actions/workflows/test.yml)

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

Dependency validation uses an iterative graph walk, so a valid native plan is not
rejected solely because its dependency chain exceeds Python's recursion limit.
Validation preserves authored part and dependency order, digests and idempotency
keys. Tests also reopen a temporary SQLite ledger and dispatch one ready part of
a deep plan through a local adapter. The preview consumer's separate 256-part
limit still applies.

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

When a running task has a verified terminal failure, record it with
`ledger.mark_failed(project_id, part_id, evidence)`. Required evidence retains
its source, locator and finding alongside the original task/worker/route identity.
The failed part is not replayed, and its unfinished dependents stay queued.
[Task results](docs/task-results.md) describes the direct transition and the
separate unknown-outcome reconciliation path. `python examples/failure_flow.py`
demonstrates it with one real authored local child failure and no remote service.

Direct `Part` and `Plan` construction accepts tuples or lists for `depends_on`,
`tags`, and `parts`, and snapshots these collections to tuples. Later edits to a
caller's lists cannot change the plan payload, digest, or dispatch instructions.
Declaration and dependency order, repeated direct tags, and the original `Part`
objects are preserved. `Plan.from_dict` keeps its existing tag normalization.

Routes accept the literal efforts `low`, `medium`, `high`, `xhigh`, `max` and
`ultra`. Each selected effort must also appear under its model in the caller's
authorized catalog. Adding `ultra` to a catalog does not select it automatically
or change the existing step-up rules; configure the desired pool, explicit route
or step-up route. An adapter remains responsible for matching these labels to
the provider it uses.

## Scope

This is a reference core, not a turnkey agent, scheduler, or deployment package. It contains no credentials, provider-specific model list, private routing policy, or live service endpoint. An integration should enforce its own authorization, rate limits, storage policy, and evidence requirements before connecting an adapter.

## Preview an authored plan

Review native plan identity, initial dependency readiness, every configured route and stable idempotency keys before attaching a Ledger or Hub:

~~~sh
python -m fanout_engine.preview --plan plan.json --routes routes.json
~~~

The command validates the entire request and writes deterministic JSON to stdout. An optional --output new-preview.json saves a new file without replacing an existing destination. [The plan preview guide](docs/plan-preview.md) provides complete input examples, the report contract, native Python helper, consumer limits and file-delivery behavior. Initial dependency readiness is separate from stored dispatch eligibility; this preview performs no dispatch or provider operation.

## Inspect a retained project

Before deciding what to dispatch or reconcile, inspect a project already recorded
in the existing ledger:

```python
from fanout_engine import inspect_project

report = inspect_project(ledger, "sample")
print(report["queued_ready_ids"])
for part in report["parts"]:
    print(part["id"], part["state"], part["unmet_dependencies"])
```

The caller supplies its existing open `Ledger` and project ID; no external Plan,
Hub or route catalog is needed. One SQL statement reads the stored plan and all
its part rows. The report preserves plan order, instructions, tags and dependency
order, native state, idempotency keys, worker/task references, route/evidence JSON,
artifact references and recorded update timestamps. It includes counts for all
six native states and each part's **direct** prerequisites that are not completed.

`queued_ready_ids` is the intersection of queued parts and parts whose direct
prerequisites are completed. `blocked_queued_ids` contains the other queued parts.
A failed or unknown prerequisite remains visible as such; no task is retried,
reconciled or reclassified by inspection. Dispatching work is not recovered or
marked unknown by this read. These are observations at the snapshot, not a
reservation, a worker/route availability check, or proof about external effects.
References and evidence are retained records; inspection does not open their
locators or authenticate their claims.

The returned JSON-compatible values are detached: changing them does not edit the
ledger or a later report. The read performs no writes. Unknown project IDs raise
`InspectionError` with code `project_not_found`; missing expected part rows use
`missing_parts`. Malformed JSON, inconsistent plan/payload/key identities,
unexpected part rows or values that cannot form finite UTF-8 JSON use
`invalid_record`. No partial report is returned on these failures. Ordinary
database errors still propagate; this is not database repair or a new storage
initialization interface.

Run a complete local mixed-state example:

```sh
python examples/inspect_plan.py
```

It builds an authored in-memory project with completed, running, unknown, failed
and queued work, then prints the report without an adapter. Only `notes` is queued
and dependency-ready; `verify`, `signoff` and `publish` show their different
unfinished prerequisites. This reference workflow does not claim production
worker capacity or installed estate integration.

For a project already stored on disk, use the read-only CLI directly:

```sh
python -m fanout_engine.inspect --database "work/dispatch.sqlite3" --project sample
```

It opens only an existing database, validates the complete retained project and
writes the native JSON report. Missing or malformed databases are not created or
initialized. [The existing-ledger guide](docs/inspect-ledger.md) explains status
codes, literal path handling, Python use and the read-only/WAL boundary.

## Compare a revised plan before recording it

```sh
python -m fanout_engine.compare --before original.json --after revised.json
```

The comparison shows complete native identities, exact part edits, additions,
removals, declaration-order changes and before/after idempotency keys. This makes
it visible when an edit changes the keys of otherwise unchanged parts. It reads
the two authored files and leaves retained state untouched. See the
[complete plan-comparison example](docs/compare-plans.md) for the report fields,
native Python helper and input limits.

## Inspect the recorded event timeline

Review the events retained before a part reached its current state:

```sh
python -m fanout_engine.history --database "work/dispatch.sqlite3" --project sample
python -m fanout_engine.history --database "work/dispatch.sqlite3" --project sample --part verify
```

The read-only command preserves recording sequence, event names, timestamps and
both exact stored JSON details and their parsed values. It validates the complete
captured project history before an optional exact part filter. A known part with
no events has an empty timeline; an unknown part is reported distinctly. The
[history guide](docs/inspect-history.md) explains the report, Python helper and
local example. Events remain recorded evidence; the command performs no dispatch,
recovery or reconciliation.
