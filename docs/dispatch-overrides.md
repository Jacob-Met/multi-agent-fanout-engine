# Explicit routes for one dispatch call

Pass `explicit_routes` when a particular authored part needs a particular
authorized route:

```python
dispatch_ready(
    plan, ledger, hub, router,
    worker_for=lambda part: "worker-a",
    explicit_routes={"review": Route("model-a", "high")},
)
```

The keys must be exact part IDs from this plan and every value must be a native
`Route`. `None` or omitting the whole argument means no overrides; an empty
mapping also uses the normal pool. A `None` value inside a mapping is invalid.
Misspelled IDs, non-route values, and non-mapping arguments raise `ValueError`
before the dispatcher records the plan, selects a worker, or calls the Hub.
An existing ledger's rows and events remain unchanged on these refusals.

The dispatcher captures the mapping at the start of the call. A worker-selection
callback or Hub adapter can change the original caller mapping, but that change
does not replace this call's explicit choices. A later call receives whatever
mapping the caller passes then. This does not freeze or clone the router.

Route authorization retains its existing timing: the router validates the
selected route when an eligible queued part is reached. A known part that is
already in flight or blocked by dependencies is not routed merely because it
has an override. An unauthorized selected route can still refuse after earlier
parts have started; their accepted or unknown outcomes remain recorded, and
the dispatcher does not replay them. Explicit overrides retain precedence over
the default pool, and parts without an override keep their normal stable choice.

## Verification

On original main `0b169f9df939350911d76dbda88023fe37ee53bf`, a local recording
Hub received default-low submissions for both `alpha` and `beta` when the caller
passed `{"alpah": Route("model-a", "high")}` or `{"alpha": None}`. The
valid `{"alpha": Route("model-a", "high")}` control selected high for alpha
and low for beta. The repair refuses the first two inputs before any submission.

`tests/test_dispatch_overrides.py` covers these refusals, exact identity checks,
ordinary/false-valued mapping implementations, retained choices during callback
mutation, reopened SQLite preservation, and unchanged authorization timing.
The tests use temporary SQLite databases and local recording adapters. They do
not call a model provider, remote worker, or production service.
