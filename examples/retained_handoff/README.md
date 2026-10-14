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

## Open an offline review of the completed run

From this checkout's repository root, render the retained database to a new HTML
file outside the run directory:

```bash
python3 -B -m fanout_engine.review --database ../fanout-handoff-run/retained.sqlite3 --project fixture-handoff-51df5b72e832 --output ../fanout-handoff-review.html
```

Open `../fanout-handoff-review.html` in a browser. The self-contained page shows
recorded states, dependency readiness and complete part details. Its ordinary
download link saves the exact native inspection JSON, including the final
newline. The command reads the existing ledger and refuses an occupied output
path; it does not dispatch, retry or reconcile work.

The public all-phase run retains its completed database. Rendering that database
shows the current completed observation; it does not reconstruct an earlier
phase from the saved inspection reports. Those JSON reports remain the earlier
observations. If reviewing databases from separate executions, label them
separately rather than presenting them as successive snapshots of one run.

See the [offline retained-project review guide](../../docs/project-review.md)
for the report's read-only scope and output behavior. The page is a fixed
observation: later database changes require a new report at a new output path.

## Open the four saved phase reviews

A new public run also writes four self-contained offline pages while each phase's
retained state exists. Open a page directly in a browser; no server is required.

| Page in the run directory | Recorded phase | Events | Completed | Unknown | Queued |
| --- | --- | ---: | ---: | ---: | ---: |
| `initial-review.html` | Initial independent work | 9 | 2 | 1 | 2 |
| `unknown-review.html` | Resume completes summary; audit remains unknown | 12 | 3 | 1 | 1 |
| `held-review.html` | Hold preserves the unknown result without replay | 12 | 3 | 1 | 1 |
| `final-review.html` | Evidence-backed reconciliation and handoff | 16 | 5 | 0 | 0 |

These four pages come from **one execution** of the documented public command.
They are saved observations and do not update as the retained database changes.
The initial page records summary as ready and handoff as blocked. The next two
keep handoff blocked by the unknown audit; their complete saved inspections are
identical. The final page records all five parts completed. The audit's task
reference remains null throughout: reconciliation does not invent a task ID.

Each page's **Download exact inspection JSON** link contains the exact bytes of
its sibling `<label>-inspect.stdout.json`, including the final newline. The
phase receipt binds the actual review command, empty raw stdout/stderr, page
SHA-256 and inspection SHA-256. The final `receipt.json` lists `review_reports`
in initial, unknown, held, final order. Keep each HTML file with its matching
inspection and phase receipt when sharing the observations. The renderer and its
read-only interpretation are documented in [project review](../../docs/project-review.md).

The separately qualified earlier two-page artifact still describes two separate
executions. These new same-run captures do not change that earlier provenance.

A capture failure is not a transaction rollback. Each phase can have committed
its local work before the review command, output publication or byte comparison
fails. A failed phase retains its started marker and any files already written;
it does not get a successful phase receipt. Inspect the retained database and
raw diagnostics before deciding how to proceed. The public command refuses an
already existing run directory before phase work; do not reuse its private
`--phase` option as a retry mechanism or overwrite an existing review page.

For a literal comparison of saved observations, the separate
[saved-inspection comparator](../../docs/compare-inspections.md) reads only the
two JSON files. For example, from the repository root, replace `RUN` with the
run directory and choose new output paths:

```sh
python3 -B -m fanout_engine.compare_inspections --first RUN/initial-inspect.stdout.json --second RUN/final-inspect.stdout.json --output RUN/initial-final-comparison.json
python3 -B -m fanout_engine.compare_inspections --first RUN/unknown-inspect.stdout.json --second RUN/held-inspect.stdout.json --output RUN/unknown-held-comparison.json
```

The first/second roles are explicit. The comparator describes saved values; it
does not read the ledger, infer progress from timestamps or perform work.

## Open the saved comparisons from a new run

After all four phases complete, the same public command now creates two readable
comparison pages and their exact native JSON files. No extra comparison command
is needed for a new run.

| Open in the run directory | First saved inspection | Second saved inspection |
| --- | --- | --- |
| `initial-to-final-comparison.html` | `initial-inspect.stdout.json` | `final-inspect.stdout.json` |
| `unknown-to-held-comparison.html` | `unknown-inspect.stdout.json` | `held-inspect.stdout.json` |

Open either HTML file directly in a browser. The matching `.json` sibling
contains the complete native comparison. The page's download link provides
those exact JSON bytes, including the final newline. First and Second retain
their explicit input roles; the comparator describes saved values without
reading the ledger, dispatching work or inferring chronology from timestamps.

The initial/final report shows changes to audit, summary and handoff. The
audit's task reference remains null even when its state is completed. The
unknown/held report confirms identical saved input bytes and values, with no
changed fields or parts. These pairs belong to this one authored local run;
they do not change the earlier separate-execution review artifact.

The final `receipt.json` adds `comparison_reports` in the table's order. Each
entry binds the two inspection filenames and SHA-256s, both output filenames
and SHA-256s, and the actual JSON/HTML commands, exit codes and raw stream
hashes. The eight `*-comparison-{json,html}.{stdout,stderr}.log` files retain
the command streams. Successful explicit-output commands leave those streams
empty. Every file present before the comparison step is checked for unchanged
bytes afterward, including the database, journals, phase pages and raw reports.
The existing checkout source checks also surround each comparison command.

A comparison failure occurs **after the native phases have committed their
work**. It does not roll back that work or invalidate the completed phase
receipts. Partial comparison files and diagnostics remain available, but a
successful overall `receipt.json` is not written. Preserve the directory for
inspection; the public command refuses to reuse it. The private phase option
is not a report retry mechanism. For an existing run, the separate commands
above remain available with new output names; add `--format html` for a readable
page. See the [saved-inspection guide](../../docs/compare-inspections.md).

A focused maintained receiving test invokes the public workflow once and
checks the new outputs against its actual saved inspections and retained
references, then confirms an occupied output directory stays unchanged:

```bash
python3 -B -m unittest discover -s tests -p 'test_retained_handoff_comparisons.py' -v
```

This remains the authored local adapter example with five unique calls, no
audit replay, four existing phase reviews and sixteen final events. It adds
no provider, installed service or live status view.

## Select an aggregate phase deadline

The public command waits up to 30 seconds for each of its four existing child
phases by default. A phase performs several bounded native reads in addition to
its local work. On a slower computer, choose a larger aggregate phase budget
explicitly, always using a new output directory:

```sh
python3 -I -B examples/retained_handoff/run_consumer.py --phase-timeout-seconds 180 --output ../fanout-handoff-run-180
```

`--phase-timeout-seconds` accepts a finite numeric value greater than zero and
at most 3600 seconds (sixty minutes). Fractions are allowed. Zero, negative,
non-finite, over-limit and malformed values are input errors before any output
directory or phase work is created. Omitting the option retains the existing
30-second behavior; there is no option to disable the deadline.

This setting controls only the parent's aggregate wait for each phase child.
Every individual inspection, route, blocker, review and comparison CLI retains
its separate 15-second limit. The setting is not a whole-command deadline and
does not promise that a slower individual reader will succeed. The four final
comparison commands execute after the four phases, under their existing limits.
The successful final receipt records `phase_timeout_seconds`, and each phase
command record records its `timeout_seconds`.

A timeout does not roll back local work that the phase has already committed.
Preserve the partial directory and diagnostics. This option adds no automatic
retry, resume or private-phase recovery; do not reuse an existing directory or
its private `--phase` argument as a retry mechanism.

The focused argument and propagation checks do not dispatch fixture work. They
exercise actual CLI input errors/help and stop the real public runner at its
first subprocess boundary before a child is launched:

```sh
python3 -B -m unittest discover -s tests -p 'test_retained_handoff_phase_timeout.py' -v
```
