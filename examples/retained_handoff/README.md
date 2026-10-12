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
