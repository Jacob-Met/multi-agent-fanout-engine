# Authored fanout-plan preview: proposed consumer contract

Status: original native API and absent-command witness are complete; no product source is authored. Root claim and contract review precede implementation.

Repository: `Jacob-Met/multi-agent-fanout-engine`; main `d65bde9c59b1d2593a80f6d838c0a40bf6768013`, tree `d5e5ad4e316be0b20a50151f8549ac490d3d99de`.

## Exact fence

New `fanout_engine/preview.py`, `tests/test_preview.py`, and `docs/plan-preview.md`; one additive README section and unique `docs/qualification/plan-preview-0ee86eaeaf8d/` evidence. Direct import from the new module; no `__init__.py` export change. Preserve the retained-inspection owner's `ledger.py`, `inspection.py`, `__init__.py`, `examples/inspect_plan.py`, `tests/test_inspection.py`, and README additions. Native Plan, Route, EffortRouter, dispatch, manifests, dependencies and workflow are unchanged.

## Native helper

`preview_plan(plan: Plan, router: EffortRouter, *, explicit_routes: Mapping[str, Route] | None = None) -> dict`

Consume actual native objects. Reject an unknown explicit part key or a non-Route explicit value. Visit every part in authored declaration order, including parts with unfinished dependencies; call `router.route_for(part.id, explicit_routes.get(part.id))` and `plan.idempotency_key(part.id)`. Report `plan.to_dict()` and `plan.digest` unchanged. Initial readiness is exactly `[part.id for part in plan.ready_parts(())]`. No completed IDs are accepted in this pre-dispatch consumer. Read configured `router.step_up` as metadata only; never call `step_up_after_refusal`. Validate the entire report before returning it.

The helper returns this document (illustrative scalar values):

```json
{
  "schema_version": 1,
  "plan": {"project": "review", "parts": []},
  "plan_digest": "native digest",
  "dependency_ready_without_completions": ["part-a"],
  "routes": [
    {
      "part_id": "part-a",
      "route": {"model": "model-a", "effort": "low"},
      "route_source": "pool",
      "idempotency_key": "native key"
    }
  ],
  "configured_step_up": null
}
```

`route_source` is exactly `explicit` when that part has an explicit mapping entry, otherwise `pool`. `configured_step_up` is null or a model/effort object. These are configured choices, not an authorization or capacity observation. The empty parts list above only abbreviates the shape; native Plan admission still requires a nonempty plan.

## CLI input

`python -m fanout_engine.preview --plan plan.json --routes routes.json [--output new-preview.json]`

The plan file is decoded as UTF-8, parsed through native `strict_json_loads`, then passed through native `Plan.from_dict`; this preserves native normalization, dependency/part order, digest and key calculation.

The routing JSON must be an object with exactly required `catalog` and `pool`, and optional `explicit_routes` and `step_up`. `catalog` is a nonempty object mapping model strings to nonempty lists of effort strings. Every declared pair is validated through native `Route`; the caller-supplied catalog does not prove real provider authorization. `pool` is a nonempty ordered array of exact `{model, effort}` objects. `explicit_routes` is an object keyed only by this plan's part IDs, with the same exact route objects; omission means no overrides. `step_up` is omitted, null, or one exact route object. Native `EffortRouter` validates all configured pool, step-up and explicit routes against the supplied catalog. Reject unknown fields, duplicate JSON keys, malformed shapes and any unauthorized explicit route before a success document.

Consumer limits: at most 1 MiB plan input, 256 KiB routing input, 256 parts, 256 catalog models, 256 pool routes, and 4 MiB serialized report. The 256-part limit keeps the inherited recursive DAG validator bounded without changing native core policy. Read regular files with capped reads; treat deep/malformed JSON, native validation and I/O errors as clean refusals. These are preview consumer bounds, not a new bound on Plan or the dispatcher.

## CLI output and delivery

The CLI adds `input_sha256: {plan: <raw-byte SHA256>, routes: <raw-byte SHA256>}` to the native-helper document. The hashes bind the exact captured input bytes; the plan digest binds the native normalized plan. Do not claim a cross-process input lease. Report no timestamp, absolute path, cost, queued/dispatchable state or execution receipt. Serialize the complete report through native `canonical_json` plus one LF; identical captured inputs produce identical output bytes.

With no output path, write the complete validated report to stdout. A broken output stream can deliver a prefix and is an I/O failure, not successful preview delivery. With `--output`, require an existing destination parent and an absent destination, including refusing existing files, directories and symlinks. Stage the complete report in that parent, flush/fsync, publish with a no-clobber hard link, then remove only the owned stage. Unsupported link publication refuses rather than silently replacing anything. File mode emits no success stdout; there is no second status-output step after publication. Validation and pre-publication delivery failures preserve prior files; failure after an actual publication cannot be described as proof of no delivery.

## Frozen original witness

`baseline-native/receipt.json`: SHA256 `1d5df58bef3b0e884d0a8d5355df1d01a7094a77c32e84f1ce2eb964d67d7a03`, Git `d1db605c20adb64e47997ffd38f5394f9cf034b2`.

Two real Python 3.12.14 processes: one imports and executes the native Plan/Route/EffortRouter APIs for five parts, one observes the proposed module command absent. The first returns the actual native digest, all five routes and keys, and `research, notes` as initial-ready; the second exits1 with no module and preserves a preseeded output. The source/input/output byte custody matches before/after. No Ledger/Hub instance, sqlite connection, socket or child launch occurs in the native API process. The original witness is retained and will not be rerun merely to reproduce unchanged evidence.
