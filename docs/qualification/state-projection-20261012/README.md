# Read only the state for per-part eligibility

`Ledger.part_state(project_id, part_id)` now selects the stored state column
directly. A retained part can carry a large payload or evidence document; the
existing per-part dispatch check previously loaded that complete row for every
state lookup. The public method, current-state behavior, and missing-row error
are preserved.

## Source scope

The production change is confined to `Ledger.part_state` in
`fanout_engine/ledger.py`. It keeps the existing connection context manager,
project/part predicates, and `LedgerError("part is not in the ledger")` for a
missing row. `part()` still loads the full record when its caller needs it.
Dispatch continues to read each candidate's current state and then use the
existing transactional admission guard.

The measured parent is `ae23e21d10c61b22397378a6974db6992e6c1806`, including
the accepted constructor snapshots, per-part eligibility, failed-COMMIT cleanup,
read-only inspection CLI, and unreadable-acknowledgement guard. The parent ledger
blob is `df0f3c6e1fa37546ec48129b515317cabb530619`; the candidate ledger blob is
`3efb4947545988de468a67dc1265d51151716a42` (SHA-256
`762d038419afb9f9a41a388ded84f361c0ccbea49bf9bd46ba266478660037bf`).
All other production source from that parent is unchanged.

## Consumer verification

The complete maintained course passes **105 tests**: the parent's 102 methods
plus three new state-reader controls. Those controls exercise native transitions
through all six states, disk close/reopen, large retained Unicode evidence,
fresh observation of another connection's transition, exact project scope,
missing-row diagnostics, and dispatch refusal at a missing row before later
submissions. The new controls also pass on the unchanged parent behavior; this
increment improves the read cost while preserving that behavior.

The existing eligibility tests continue to exercise later-part claims from
another connection, the race after the state read, dependency unlocking only on
the next pass, and unknown/in-flight no-replay. Accepted COMMIT-failure and
read-only CLI tests remain in the complete run. No Hub/provider is contacted.

A separate reviewer accepted the exact ledger delta and received both versions
with ten independent read-only disk controls. All six states, missing project
and part errors, the complete inspection report, and database bytes matched.
Their SQLite authorizer observed reads of all twelve part columns in the parent
and only the project, part, and state columns in the candidate.

## Paired disk receiving

[`measure_state_reads.py`](measure_state_reads.py) creates an ordinary native
128-part ledger with short instructions, dispatches to a local recording Hub,
and retains half the parts as completed and half as outcome-unknown. Each part
has synthetic evidence with either a one-byte or 256-KiB finding. Fixture
creation uses the real public ledger transitions; its separate cost is recorded.

Each source then receives **the same database** in a fresh Python process.
Before/after order alternates over three pairs. The measured workflow constructs
the Plan, opens the saved ledger, performs three no-work `dispatch_ready` passes,
inspects the complete project, serializes the report, and closes the ledger.
Every pass retains the unknown/completed states and makes zero Hub calls.

The six processes for each fixture produce identical complete report hashes and
leave database bytes unchanged. Timings below are medians on CPython 3.12.14 and
SQLite 3.53.1 in a shared Linux environment; raw samples and source hashes are in
[`paired-receiving.json`](paired-receiving.json).

| Finding per part | First dispatch, before → after | Plan/open + three passes | Complete workflow with inspection/serialization |
|---|---:|---:|---:|
| 1 byte | 1.080 → 0.876 ms | 4.347 → 3.522 ms | 10.573 → 9.750 ms |
| 256 KiB | 23.405 → 0.882 ms | 70.681 → 3.562 ms | 457.350 → 360.148 ms |

The larger fixture occupies 67,342,336 bytes including retained event evidence.
In a separate diagnostic pass over the same 128 state lookups, the text returned
by SQLite to Python falls from **33,602,816 to 1,536 UTF-8 bytes**. Traced peak
Python allocation for that loop falls from **283,408 to 19,966 bytes**, including
the collected state results. These diagnostics do not instrument the timed
samples. Both versions still perform 128 indexed point lookups.

Full inspection intentionally validates and serializes the retained evidence.
Its cost remains visible in the complete-workflow column and is unaffected by
this method's projection. Filesystem caches and shared-host contention can move
the observed timings; the exact report/database comparisons and reduced returned
data are the stronger bounds on this narrow change. This measurement does not
qualify concurrent throughput or a remote provider.

## Reproduce

From the candidate repository, with an unchanged parent checkout available:

```sh
python -m unittest discover -s tests -v
python docs/qualification/state-projection-20261012/measure_state_reads.py \
  --before /path/to/ae23e21-parent --after . \
  --parts 128 --passes 3 --repeats 3 --finding-bytes 1 262144 \
  > /tmp/state-projection-results.json
```

The benchmark uses temporary databases and local Hub fixtures. It has no timing
pass/fail thresholds and makes no workflow, Actions, or service changes.
