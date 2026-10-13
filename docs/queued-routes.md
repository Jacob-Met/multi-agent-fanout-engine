# Preview routes for queued work in a retained ledger

Use this command when a plan is already recorded and you want to review the
configured routes for work that is queued and dependency-ready now:

~~~sh
python -B -m fanout_engine.queued_routes \
  --database work/dispatch.sqlite3 --project sample --routes routes.json
~~~

Python 3.10 or newer and the standard library are sufficient. Run from this
source checkout. The database must already exist; the command does not initialize
one. The project identifier is exact. Each of the three required options occurs
once; unknown, abbreviated or repeated options refuse before file access. Use
`--project=VALUE` or the analogous equals form when an operand begins with a
hyphen. Help reads no database or routing file.

The command writes a JSON report to stdout. There is no output-file option.
Shell redirection is a separate caller operation: never redirect stdout onto the
database, a SQLite sidecar, the routing input or another file you need to retain.

## What this adds

The [authored-plan preview](plan-preview.md) shows initial dependency readiness
without a ledger. The [retained-project inspector](inspect-ledger.md) shows
recorded states without checking a route catalog. This command combines one
validated retained snapshot with caller-supplied routing configuration.

For example, the [retained handoff](../examples/retained_handoff/README.md) starts
with audit, inventory and notes eligible. After its first local-adapter phase,
audit is unknown, inventory and notes have completed, and only summary is queued
and ready. After summary completes, no part is ready until the audit is
reconciled. This command reports the routes for that current readiness; it does
not reuse the initial preview's ready list. A completed handoff has no selected
routes.

This is an advisory observation, not a dispatch reservation. It checks configured
model/effort labels against the supplied catalog. It does not contact a provider,
verify provider authorization or capacity, select a worker, inspect an artifact
locator, authenticate evidence, dispatch, retry, reconcile or execute step-up.
A later dispatch must make its own current eligibility and authorization checks.

## Routing input

Use the same strict routing JSON schema as the authored preview:

~~~json
{
  "catalog": {"fixture-local": ["low", "ultra"]},
  "pool": [{"model": "fixture-local", "effort": "low"}],
  "explicit_routes": {
    "audit": {"model": "fixture-local", "effort": "ultra"}
  },
  "step_up": {"model": "fixture-local", "effort": "ultra"}
}
~~~

These are fictional route labels, not a provider configuration. Every explicit
part ID must belong to the selected retained plan. Every explicit route must be
authorized by this catalog, including routes for completed, blocked or uncertain
parts and when the ready list is empty. This whole-configuration preview check
is deliberately stricter than the dispatcher's selected-only authorization
timing; it does not change dispatch behavior.

Selected parts use the existing deterministic per-part pool choice unless an
explicit override exists. Configured step-up is validated and shown as metadata
only. All route fields, efforts, strict JSON rules, catalog and pool admission
come from the existing preview/router implementation.

The routing file is captured once as a bounded regular file, then its exact raw
bytes are hashed. The ledger snapshot and routing file are separate captures,
not one cross-resource transaction.

## JSON report

| Key | Meaning |
| --- | --- |
| `schema_version` | `1` |
| `project_id`, `plan_digest` | Exact retained native identity |
| `state_counts` | Counts for all six native states, including zero counts |
| `queued_ready_ids` | Queued parts whose direct prerequisites are completed |
| `blocked_queued_ids` | Other queued parts |
| `parts` | Every part in retained declaration order, with `id`, `state` and exact direct `unmet_dependencies` |
| `routes` | Ready parts in retained declaration order, each with `part_id`, `route`, `route_source` and stored native `idempotency_key` |
| `configured_step_up` | Validated model/effort object or `null`; never executed |
| `routing_input_sha256` | SHA-256 of the exact captured routing file bytes |

Each route contains `model` and `effort`; its source is `explicit` or `pool`.
An unmet dependency contains its exact `id` and current native `state`.
Unknown, failed, running, dispatching and completed parts remain visible as
context, but never receive a selected route. An empty route list is a valid
successful report, not evidence that the project succeeded.

The command reuses `inspect_project` once. That function validates the complete
stored plan and all parts in one SQL statement before projection. The new
consumer uses the already-validated stored keys and digest; it does not
reconstruct or normalize a Plan. Instructions, tags, worker/task references,
evidence and artifact locators are not copied into this smaller report.

## Read-only and failure boundaries

The CLI uses `Ledger.open_readonly`, with the existing regular-file and literal
filesystem-path handling. It issues no SQL writes, recovery transitions or
schema creation. Normal SQLite locking and WAL visibility remain in effect;
read-only SQLite can interact with shared-memory bookkeeping. This is not a
promise that every filesystem byte around an active database is immutable.
A busy or concurrently changing database is not repaired or reserved.

The routing file is limited to 256 KiB; catalog and pool each accept at most
256 entries. This consumer accepts at most 256 retained parts and a complete
UTF-8 report of at most 4 MiB, including the final LF. These consumer limits do
not bound the database file size or the memory used by the underlying whole
snapshot validation. Read only trusted authorized databases.

| Exit | Meaning |
| --- | --- |
| `0` | Complete advisory JSON, including no ready work, or help |
| `1` | Stdout write/flush failure |
| `2` | Usage, routing admission, database/read or malformed-record failure |
| `3` | The exact requested project is not recorded |

Validation and encoding finish before success output starts. A failed output
stream may already have received a prefix; exit 1 is not an atomic output
publication. Errors go to stderr. No partial success JSON is emitted for input
or record validation failures.

## Native Python helper

~~~python
from fanout_engine import Ledger, EffortRouter, Route
from fanout_engine.queued_routes import queued_route_report

router = EffortRouter(
    {"fixture-local": ["low"]},
    pool=(Route("fixture-local", "low"),),
)
with Ledger.open_readonly("work/dispatch.sqlite3") as ledger:
    report = queued_route_report(ledger, "sample", router)
~~~

The helper returns the report before the CLI adds `routing_input_sha256`.
It accepts optional `explicit_routes={part_id: Route(...)}`. The caller owns
the supplied connection and any active transaction: the helper does not commit,
roll back or close it. Returned values are detached from the ledger. Changing
the report cannot update retained state.

## Qualification

The focused maintained course invokes actual CLI subprocesses and real owned
SQLite fixtures. On the received author source, eight methods passed, including
all native states/readiness, unsorted repeated native tags and exact identity,
all-override admission with no ready work, one SELECT without committing the
caller's transaction, invalid/oversized/nonregular routing, healthy recovery,
unchanged quiescent database bytes and a real failing stdout device.

Run from this checkout:

~~~sh
python -B -m unittest discover -s tests -p test_queued_routes.py -v
~~~

The initial author candidate passed those eight methods. Independent receiving
then found one additional boundary: starting Python with stdout closed returned
exit 1 through an AttributeError traceback. That first course is preserved as
41 passing checks and one failed diagnostic check. The successor adds a narrow
absent-stdout guard in this new CLI's output-error path, leaving existing preview
and all routing behavior unchanged. It also closes one SQLite test fixture
connection explicitly, as requested by peer review. A real closed-file-descriptor
regression and the two affected existing methods pass as a separate three-method
author course; this is not a claim that a new full suite ran.

The public contract and independent original-first consumer course are recorded
at [coordination comment 6142035765](https://github.com/Jacob-Met/hamon/issues/143#issuecomment-6142035765).
Independent candidate receiving and exact publication are linked separately.
The author course is not a full repository suite, native Windows/macOS,
installed estate, remote-worker or provider qualification. Existing dispatch,
inspection, routing, plan and ledger source remain unchanged.
