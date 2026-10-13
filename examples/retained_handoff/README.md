# Retain a local handoff across an unknown acknowledgement

This runnable example produces an integrity audit, file inventory, receiving
notes, summary and final handoff from three authored local files. Five parts use
the native router, dispatcher and SQLite ledger. The audit completes its local
work but returns an unreadable acknowledgement; independent work continues while
the audit remains `outcome_unknown`. Fresh Python processes reopen the ledger,
hold the unknown work without resubmitting it, then reconcile its exact completion
journal and artifact digest before finishing the handoff.

The adapter performs deterministic local file operations. `fixture-local` is an
authored model label: the audit explicitly requests the authorized `ultra` route,
and the other parts use the configured `low` pool. These labels exercise native
routing and persistence. There is no model inference, provider call, remote
worker, scheduled task, installation or deployment in this example.

## Run from a normal checkout

Python 3.10 or newer and the standard library are sufficient. From the repository
root, choose an output directory that does not exist:

```bash
python3 -I -B examples/retained_handoff/run_consumer.py --output ../fanout-handoff-run
python3 -I -B examples/retained_handoff/receive_history_cli.py --run ../fanout-handoff-run
```

The scripts locate this checkout from their own file paths, so an absolute script
path also works from another working directory. They import the checkout's
`fanout_engine` package directly; an installed copy is unnecessary.

The first command runs four bounded phases in separate Python processes. It
invokes the native preview and current-state inspection CLIs, writes a real
retained SQLite database, saves every local completion journal and artifact, and
records complete state/history reports. The second command reads the completed
database through the maintained history CLI twice, comparing the full project
and exact `audit` timelines with every selected SQLite event row. The read-only
checks verify that the quiescent database bytes stay unchanged.

Successful commands print JSON. The first receipt reports `status: completed`,
five completed parts, five unique local adapter calls, zero audit replays and
sixteen final events. The history receipt reports `decision: accepted` with
sixteen whole-project events and three audit events.

An existing output path is refused, including a directory, file or symlink. Each
internal phase also creates an exclusive started marker. If a command is
interrupted, preserve that directory for inspection and use a new directory for
a fresh demonstration. The private phase argument is for the runner's child
processes; this script does not automatically resume its own interrupted phases.

## Follow the recovery flow

| Fresh process | Work and retained state | Events |
| --- | --- | ---: |
| Start | The audit writes its artifact and journal, then its response cannot be read. The engine parks it as unknown. Inventory and notes still finish; summary becomes ready and handoff remains blocked. | 9 |
| Resume | Reopening retains the unknown audit. Only summary is submitted and completed. | 12 |
| Hold | Another dispatch pass adds no adapter calls or events. Handoff still waits for the audit. | 12 |
| Reconcile | The exact journal and artifact bytes establish the audit's local completion. `reconcile_unknown` records the evidence, then handoff runs and completes. | 16 |

The audit retains `dispatch_started`, `outcome_unknown` and `reconciled` events.
Its unknown acknowledgement is never filled in with an invented accepted task
ID. The generic engine evidence mentions remote acceptance; this adapter's work
is entirely local.

Useful files in the new output directory are:

- `artifacts/handoff.json`: the final product, linking four dependency artifacts
  by SHA-256 and summarizing the three input files, which total 447 bytes.
- `retained.sqlite3`: the durable ledger produced by this execution.
- `unknown-state.json` and `unknown-history.json`: the retained state after three
  parts complete while the audit remains unknown.
- `hold-receipt.json`: the reopened pass with zero submissions and no new events.
- `adapter-journal/` and `adapter-calls.jsonl`: the exact stable-key local
  completion records and the five actual submissions.
- `final-state.json`, `final-history.json` and `final-audit-history.json`: current
  state and the complete ordered timeline after reconciliation.
- `source.json` and `receipt.json`: the observed runtime file identities, commands
  and overall result.
- `history-cli-receiving/`: both native history reports and their receiving receipt.

## Inspect the retained result directly

From the repository root, these existing native entrypoints read the new run:

```bash
python3 -B -m fanout_engine.inspect --database ../fanout-handoff-run/retained.sqlite3 --project fixture-handoff-51df5b72e832
python3 -B -m fanout_engine.history --database ../fanout-handoff-run/retained.sqlite3 --project fixture-handoff-51df5b72e832
python3 -B -m fanout_engine.history --database ../fanout-handoff-run/retained.sqlite3 --project fixture-handoff-51df5b72e832 --part audit
```

The [existing-ledger guide](../../docs/inspect-ledger.md) covers state inspection,
and the [history guide](../../docs/inspect-history.md) explains retained events,
read-only behavior and report errors. The smaller
[`create_retained_ledger.py`](../create_retained_ledger.py) example builds authored
mixed states directly. This example supplies a completed, multi-process adapter
workflow that those same inspection entrypoints can receive.

## Source identity and adapting a caller

Each new run records SHA-256 and Git blob identities for the checkout's Python
engine modules, this example's Python scripts and its fixtures. The manifest
uses relative paths, so the checkout and completed run can be moved together.
Child phases and the history receiver require the same recorded input bytes;
changes between checks are rejected. The record observes local files, including
any local edits. It does not attest a Git commit or authenticate a deployment.
The small authored fixture pin is also checked before dispatch.

The integration points in [`run_consumer.py`](run_consumer.py) use public APIs:
`Plan.from_dict`, `EffortRouter`, `dispatch_ready`, `Ledger.mark_completed`,
`Ledger.reconcile_unknown`, `Ledger.open_readonly`, `inspect_project` and
`Ledger.events`. No engine module is copied into this directory.

For a real caller, keep the caller-authorized catalog and adapter-specific effort
mapping explicit. Replace `LocalFileAdapter` with the caller's transport, persist
completion evidence keyed by the exact native idempotency key, and validate that
evidence before recording completion or reconciliation. An unreadable response
establishes uncertainty; the verified local journal establishes completion in
this fixture. A production adapter must supply its own evidence of what its
worker or provider actually did. This example's local journal is not evidence
about any external task.

## Preview routes from each retained phase

The same public command now saves four actual
[`fanout_engine.queued_routes`](../../docs/queued-routes.md) reports alongside
the existing state and history captures. No extra setup or command is needed.
Each report uses the retained database and the checked fixture routing file:

| Capture | Selected routes | Retained context |
| --- | --- | --- |
| `initial-queued-routes.stdout.json` | `summary`, using the pool's `fixture-local / low` route | Audit is unknown; handoff is blocked. |
| `unknown-queued-routes.stdout.json` | None | Summary has completed; handoff still waits for audit. |
| `held-queued-routes.stdout.json` | None | The idle pass has not released or replayed audit. |
| `final-queued-routes.stdout.json` | None | All five parts have completed. |

The earlier `preview.stdout.json` still describes the authored plan before
execution. These four reports describe current retained readiness at their
capture points. They are advisory snapshots, not dispatch reservations or
worker/provider capacity checks.

Each phase receipt adds `queued_route_command` with the actual invocation,
return code and raw stdout/stderr hashes, `queued_route_report` with its
relative stdout filename, and `queued_route_ready_ids` in native order.
The final `receipt.json` adds `queued_route_reports`, an ordered list of the
four relative filenames above. Raw stderr logs are kept alongside the reports.

The example verifies each report against the same phase's inspection: project,
plan digest, state counts, ready and blocked IDs, and each part's unmet
dependencies. It checks the raw routing-file SHA-256 and the selected model,
effort, route source and exact stored native idempotency key. Existing checkout
source checks surround each CLI call, and the existing database-byte comparison
includes both inspection and queued-route receiving. These checks describe this
owned, ordinary SQLite fixture; they are not a general claim that every
read-only SQLite connection leaves WAL shared-memory bookkeeping untouched.

The workflow still makes exactly five unique local adapter submissions, retains
sixteen final events, and never replays audit. Dispatch, reconciliation evidence,
the source observation algorithm and the existing output-directory refusal are
unchanged. The separately owned SQLite connection-lifetime follow-up is not
included in this integration.

A focused maintained check runs the public all-phase command and verifies the
four captures and occupied-output refusal:

```bash
python3 -B -m unittest discover -s tests -p 'test_retained_handoff_queued_routes_3795.py' -v
```

Use Python 3.10+ and a writable temporary directory. The command runs only the
authored local adapter and does not contact a provider or install a service.

## Explain each retained blocker

The same run now saves four actual
[`fanout_engine.blockers`](../../docs/inspect-blockers.md) reports beside the
route captures. Open these files to see why the queued handoff remains held:

| Capture | Blocker frontier | What the retained state permits |
| --- | --- | --- |
| `initial-blockers.stdout.json` | `audit` is `outcome_unknown`; `summary` is ready and queued | Independent summary work may proceed; the audit still needs reconciliation evidence. |
| `unknown-blockers.stdout.json` | Only the unknown `audit` | Summary is complete, but the handoff must still wait. |
| `held-blockers.stdout.json` | The same unknown `audit` | The idle pass has neither replayed audit nor released handoff. |
| `final-blockers.stdout.json` | Empty | Reconciliation and the existing handoff have completed all five parts. |

The initial handoff's direct unmet dependency order is `audit, summary`.
After summary completes it is only `audit`. Frontier rows retain the exact
recorded state and worker/task references; the unknown audit has no invented
accepted task ID. These are captured observations, not instructions to retry,
reconcile or dispatch.

Each phase receipt adds `blocker_command`, containing the actual command,
return code and raw stream hashes; `blocker_report`, its relative stdout
filename; and `blocker_frontier_ids`, the ordered frontier IDs. The final
`receipt.json` lists the four filenames in `blocker_reports`. Matching raw
stderr logs are retained beside each report.

The runner compares the entire report with the authored phase's expected
frontier and the existing validated state. Existing checkout-source and
database-byte fences cover the new native CLI reads. The queued-route captures,
local artifacts, five unique submissions, zero audit replays and sixteen final
events retain their existing behavior. No extra setup or user command is needed.

The focused regression receives the actual public workflow and then verifies
that an occupied output directory is refused without changing its contents:

```bash
python3 -B -m unittest discover -s tests -p 'test_retained_handoff_blockers.py' -v
```

This remains an authored local adapter example. It does not identify a deployed
estate ledger, contact a provider or qualify the separately owned SQLite
connection-closure follow-up.
