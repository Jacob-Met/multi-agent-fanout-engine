# Keep dispatch payloads bound to their recorded identity

`dispatch_ready` records a plan and its stable keys before submitting eligible
parts. The payload supplied to a worker selector or Hub must describe that same
validated plan. Otherwise a callback can receive different instructions from
the ones associated with its idempotency key and retained ledger.

Ordinary native `Plan` and `Part` objects are frozen. Their values, object
identities, declaration order, dependency order and repeated tags retain their
existing behavior. The dispatcher does not reconstruct these native plans.

The native Plan constructor also historically admits mutable Part-like objects.
For the standard Plan class containing these objects, dispatch captures their
native fields into immutable Parts before recording the plan or invoking
callbacks. It checks that
the captured plan digest still equals the original validated digest. If the
source has changed, it raises `PlanError` before ledger rows/events, worker
selection, route selection or Hub calls occur. The original objects remain
unchanged by the dispatcher.

Construct a new Plan when you intend to submit edited content. If its project
identifier is already retained with a different plan digest, the existing
ledger conflict rule still refuses it. The dispatcher does not reinterpret an
old key as permission for a revised task.

Callbacks and adapters receive the captured native Part fields. Later edits to
the caller's mutable sources cannot rewrite this dispatch call's submitted
payloads, readiness or keys. Custom attributes on a Part-like object are not
copied; keep additional adapter data separately, keyed by the part ID. A later
call checks the source that the caller passes then.

Custom Plan subclasses retain their existing readiness, identity and other
methods. They do not use this capture path; dispatch does not replace their
custom eligibility decisions with standard Plan behavior.

This capture does not freeze the router, worker catalog, Hub or ledger state.
Existing route authorization and transactional admission keep their timing.
Accepted and unknown submissions remain recorded, and an unknown submission
still requires evidence-based reconciliation before any retry.

## Local regression receiving

Run from the repository root:

```sh
python -B -m unittest discover -s tests -p test_dispatch_plan_snapshot.py -v
```

The tests use the real in-memory SQLite Ledger and local recording adapters.
They cover stale source refusal before effects, changes during worker and Hub
callbacks, exact submitted-versus-retained payload/key agreement, unknown-state
no-replay behavior, and unchanged native Part identity. They perform no model
inference or remote submission.
