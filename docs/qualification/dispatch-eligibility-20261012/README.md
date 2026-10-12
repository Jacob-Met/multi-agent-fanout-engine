# Per-part dispatch eligibility

`dispatch_ready` now reads the state of the candidate it is about to dispatch,
using the existing `(project_id, part_id)` primary-key lookup. Previously, it
read the complete set of queued part identifiers again for every ready part.
That repeated scan also affected a later pass where every part was already
running and there was nothing left to submit.

The production change is one eligibility condition in `fanout_engine/dispatch.py`.
Each candidate still gets a fresh state check when reached. The existing
`mark_dispatching` transaction still owns the atomic admission, so another
connection claiming the same part after the read still prevents local submit.
The completed-prerequisite snapshot and authored iteration order are unchanged.

## Source and behavior

Original source is commit `0317b4bc80638a8e952857aa5966b0e20d1fab72`, tree
`35dc556c1309b394c6f864fd5aaa6f7e7fcc0b22`. The corrected dispatch module's SHA-256
is `f6fe045bce47dc333c9e582cd0492257d1674ae073e9ac4bc33a4681696e1f3c`.
Plan, Ledger, routing, inspection and workflow files are unchanged from that
parent. No API or caller changes are required.

The original maintained suite passes 69 tests. The candidate suite passes 73.
The four added receiving tests also pass against the original source, showing
that the optimization retains these behaviors:

- Reopened running, dispatching, unknown, failed and completed records remain
  untouched. New work uses the same authored order, route, worker and stable key.
- Another connection may claim a later candidate during an earlier adapter call;
  the current pass observes that claim and skips the part.
- A claim after the eligibility read is rejected by the original atomic
  admission before this caller invokes the adapter. Recovery still parks that
  interrupted dispatch as unknown, and a later pass does not replay it.
- A prerequisite completed during the pass unlocks its dependent on the next
  pass, preserving the existing completed-state snapshot.

## Measured complete-workflow cost

[The runnable receiver](measure_dispatch.py) measures new temporary on-disk
SQLite databases with local accepting adapters. It runs each source in its own
fresh process, alternates before/after order, and repeats each size three times.
Each paired run compares complete reports, adapter calls, inspected saved
records and event history after removing only recorded timestamps. All nine
pairwise semantic hashes match. Source-file hashes are checked before and after
the experiment.

The total includes native plan construction, first dispatch, closing and
reopening the ledger, `inspect_project`, a second dispatch that must submit
nothing, and an event-history read. It excludes process startup, temporary-file
cleanup and the final result comparison. The retained receipts record CPython
3.12.14 and SQLite 3.53.1 on Linux; these local wall-clock results vary with
storage, machine load and interpreter version.

| Independent parts | Original total, median | Corrected total, median | Total speedup | Original no-work pass | Corrected no-work pass |
| --- | ---: | ---: | ---: | ---: | ---: |
| 500 | 0.405 s | 0.294 s | 1.38× | 0.0246 s | 0.00384 s |
| 1,500 | 1.951 s | 1.032 s | 1.89× | 0.237 s | 0.0119 s |
| 3,000 | 5.287 s | 1.286 s | 4.11× | 1.004 s | 0.0238 s |

See [all measurements and exact source hashes](paired-receiving.json). These
measure the local reference core. They make no claim about model-provider
latency, live worker throughput or installed estate capacity. Other costs,
including plan identity validation and inspection, remain in the total.
The fixture instructions are short. The existing per-part lookup retrieves the
complete stored row, so unusually large payloads may narrow these gains; this is
not a claim that every workload becomes faster.

Independent source review also compared 48 authored random DAG/mixed-state
cases, covering 1,026 parts and 162 local adapter submissions. Two dispatch
passes with close/reopen retained exactly equal calls, reports, snapshots and
events against the original under a fixed fixture clock.

## Reproduce

From a checkout containing this change, create a separate original worktree and
use a new output path:

```sh
git worktree add --detach /tmp/fanout-eligibility-before 0317b4bc80638a8e952857aa5966b0e20d1fab72
python -m unittest discover -s tests -v
python docs/qualification/dispatch-eligibility-20261012/measure_dispatch.py \
  --before /tmp/fanout-eligibility-before --after . \
  --output /tmp/fanout-eligibility-receiving.json
```

The benchmark uses the standard library and temporary databases, exits on any
semantic mismatch, and refuses to replace an existing output file. Production
consumers continue to use the same `dispatch_ready(plan, ledger, hub, router,
worker_for=...)` call and their existing authorized adapters. Unknown outcomes
retain their existing evidence-based reconciliation requirement.
