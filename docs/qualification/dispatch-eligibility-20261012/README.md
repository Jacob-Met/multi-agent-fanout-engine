# Indexed per-part dispatch eligibility

## Change and source

Original source is `0317b4bc80638a8e952857aa5966b0e20d1fab72` in
`Jacob-Met/multi-agent-fanout-engine`. The only production change replaces the
complete queued-set membership read in `dispatch_ready` with the existing
indexed `Ledger.part_state(project_id, part_id)` read for the current part.

The read still happens separately for every eligible iteration. An adapter can
advance a later row while an earlier part is submitted, and that later part is
then skipped. The existing transactional `mark_dispatching` remains the final
admission guard. Initial dependency readiness, authored iteration order, routes,
worker selection, idempotency keys, unknown-outcome handling and reconciliation
remain unchanged for valid recorded plans. No queue snapshot is cached.

| Source | Git blob | SHA-256 |
| --- | --- | --- |
| Original `fanout_engine/dispatch.py` | `d127a4bb6e9ea772c7c5bc8e93c5f7a5de739f06` | See pinned original tree |
| Candidate `fanout_engine/dispatch.py` | `18897c1af7d0646029889c34e3f2443339d8c850` | `f6fe045bce47dc333c9e582cd0492257d1674ae073e9ac4bc33a4681696e1f3c` |

One malformed-ledger behavior changes: if a ready part named in the recorded
plan has no stored row, the existing `LedgerError("part is not in the ledger")`
now propagates at that part instead of silently skipping it. The maintained
test deletes the first row and verifies an error before any submission. This
does not turn dispatch into whole-ledger validation; earlier valid parts may
already have been submitted before a later missing row is encountered.

The accepted Plan snapshots, finite-JSON parser, iterative graph validation and
interrupted-body rollback remain exact. The independently owned COMMIT-failure
follow-up is outside this increment. The scoped claim and owner non-overlap are
recorded in [PR12's coordination comment](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/12#issuecomment-6132103188).

## Maintained qualification

On local Linux CPython 3.12.14, the original suite passed all 69 tests. The
candidate passes all 72 tests, including three new methods in
`tests/test_dispatch_eligibility.py`:

- An earlier adapter callback advances a later row into each of the five
  nonqueued states. The later row and its evidence remain intact; unrelated
  queued work is submitted once with the same route, worker and key. A second
  dispatch submits nothing again.
- A worker-selection callback advances the current row after its eligibility
  read. Transactional admission still raises before the adapter is called.
- A missing first ready row raises the existing ledger error without a
  submission or an extra event.

The first two methods, including all five callback states, also pass against
unchanged original source. The missing-row method fails there because the
original silently skips that row. This explicitly retains the behavioral
boundary rather than claiming all malformed inputs behave identically.

An independent native Linux receiver on CPython 3.14.4 passed the 69 original
tests and both original examples against the candidate. It separately passed
the three added tests against their exact frozen bytes. Its disk-backed local
artifact workflow preserved 26 completed parts across five passes, 79 recorded
events, restart behavior, unknown-outcome exclusion and explicit reconciliation.
No remote provider was called.

## Independent consumer comparison and cost

`receive_dispatch_lookup.py` was written and executed against the original
before the candidate was exposed. It compares all six states, an adapter that
changes a later candidate, an ambiguous submit callback, dependency waves,
disk reopen and absence of replay. All normalized results have the same hash
in `original-results.json` and `candidate-results.json`:
`df20dbe2a2effd43b5ddcb91c4517e982e8e35e6c5d44d4350de07ce105eb9bc`.

The 37-part query control changes from 37 complete queued-set SELECTs and 111
indexed part SELECTs to zero complete queued-set SELECTs and 148 indexed
SELECTs. Each candidate retains a fresh indexed read; query count alone is not
a latency measurement.

Each timing below is the median of three runs on CPython 3.12.14 / SQLite
3.53.1. Both sources use the same plans, local adapter, task identities and
consumer result hashes. `first` includes first plan registration and dispatch;
`pre_recorded` begins with the same plan already recorded with all parts queued.
The complete measured `dispatch_ready` call includes route/worker/key work,
ledger transitions and adapter calls in both cases. These are synthetic local
workloads, not provider throughput measurements.

| Storage | Parts | Registration | Original median, ms | Candidate median, ms |
| --- | ---: | --- | ---: | ---: |
| Memory | 64 | first | 4.16 | 4.97 |
| Memory | 64 | pre_recorded | 3.55 | 3.52 |
| Memory | 512 | first | 126.18 | 43.96 |
| Memory | 512 | pre_recorded | 141.92 | 40.57 |
| Disk | 64 | first | 34.20 | 35.64 |
| Disk | 64 | pre_recorded | 40.10 | 28.92 |
| Disk | 512 | first | 319.91 | 107.86 |
| Disk | 512 | pre_recorded | 360.45 | 118.05 |

The small first-registration cases were slower in these samples. There is no
universal latency claim. Larger local queues avoid repeated whole-queue row
loading; remaining plan-key work, transaction cost and host variability still
matter. All eight timing scenarios retain equal complete consumer hashes.

The separate native 1,024-part spot check changed full queued-set scans from
1,024 to zero and observed SQLite VM steps from 6,601,500 to 326,400. That single
sequential sample changed CPU time from 3.345s to 0.661s and wall time from
12.156s to 7.556s. It corroborates the query reduction; it is not a controlled
multi-run timing estimate or installed service capacity claim.

## Reproduce

Run the maintained tests and ordinary examples from a checkout:

```sh
python -m unittest discover -s tests -v
python examples/demo.py
python examples/inspect_plan.py
```

The retained independent receiver accepts an explicit source directory and
output path. It writes complete observations to that JSON file and prints a
summary to stdout:

```sh
python docs/qualification/dispatch-eligibility-20261012/receive_dispatch_lookup.py \
  --source /path/to/original --output /path/to/original-results.json --repeat 3
python docs/qualification/dispatch-eligibility-20261012/receive_dispatch_lookup.py \
  --source /path/to/candidate --output /path/to/candidate-results.json --repeat 3
```

Use new result paths to retain previous observations. Run it on separate
original and candidate checkouts for a comparable result.
The raw files beside this guide preserve every timing sample and normalized
consumer observation from the original qualification.

Source publication uses `[skip ci] [skip actions]`. The sole inherited workflow
is unchanged and subscribes only to push and pull_request. No hosted Actions,
live ledger, installed daemon, scheduler, provider adapter, credential or
permission change is part of this contribution.
