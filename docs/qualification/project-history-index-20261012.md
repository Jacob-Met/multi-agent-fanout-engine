# Read project history without scanning unrelated events

The retained-history consumer selects one project, but the predecessor's events
table has no project index. Its lookup examines unrelated projects' events on
every read. Writable `Ledger` initialization now ensures one index:

```sql
CREATE INDEX IF NOT EXISTS events_project_id ON events(project_id);
```

The production delta is this single statement in `fanout_engine/ledger.py`.
History queries, their complete-record validation, global sequence numbers,
JSON evidence, dispatch transitions, and the read-only opener are unchanged.

## Source identity and ordering

The measured predecessor is
`6303882e1a4a45f5952c98cdae362b869c0f11b1`, tree
`757615a3291b4880c014f4da24194af0cd676efd`. Its ledger blob is
`d602fa8b3679807456536272d4f01fa192f54f12`. The candidate ledger blob is
`d04238a78ba8bbc66ee0461158319542c5008ba1`, SHA-256
`ccaa9ef2312664b32deca4edb0e6c318375300bb0ec904c9433ba4fd3195e0d1`.

An index on the project column is sufficient: this table's `seq INTEGER
PRIMARY KEY` is its rowid, and SQLite uses rowid to order equal index values.
The queries retain their explicit `ORDER BY seq`. SQLite documents this
ordering in its [query planner explanation](https://www.sqlite.org/queryplanner.html#lookup_by_index).
The receiving controls preserve actual global sequence gaps and complete event
records rather than inferring chronology from timestamps.

## Existing files and writable initialization

`Ledger.open_readonly(path)` still performs no schema initialization. An older
saved ledger without this index remains readable through that API and the
existing history CLI. Readers do not upgrade a file implicitly.

The ordinary writable `Ledger(path)` constructor creates the index when it is
missing. This writes SQLite index pages and metadata; it does not rewrite the
logical project, part, or event rows. Later writable opens reuse the index.
Future event inserts maintain it through SQLite's normal transaction behavior.
Creating it requires the same file's writable access and may wait for SQLite
locks; the existing timeout and error propagation remain in place.

The paired fixture grew from 15,491,072 to 15,618,048 bytes, an additional
126,976 bytes for 6,004 events. Its one-time writable constructor call took
2.522 ms in this run. These are measured fixture costs, not general storage,
migration-time, or concurrent-writer guarantees.

## Maintained controls

The predecessor passes 156 tests. The candidate passes all 158 tests, including
two new consumer controls in `tests/test_event_history_lookup.py`:

- A captured predecessor SQL fixture reopens without an index through the
  read-only API, then through the writable constructor. Both projects' complete
  current-state and history reports, all original table rows, repeated native
  tags, Unicode task references, and global event gaps survive. A dispatch pass
  makes no new Hub call: completed and unknown work are retained, and the
  dependent part stays queued. Subsequent writable and read-only opens preserve
  the upgraded file's exact bytes.
- The selected four-event history is received before and after 256 unrelated
  native projects are recorded. Its complete report is identical. A broad
  SQLite VM-work bound protects the lookup from returning to a full-table scan
  without depending on elapsed time or a particular index name. On the
  predecessor, the same test fails at 3,240 steps against its 338-step bound;
  the legacy compatibility control also passes there.

The 6,227-byte SQL fixture was generated through the predecessor's native
`Plan` and `Ledger` transitions. Its SHA-256 is
`54c93ddc03920fb36b572019eed8166792b7fe92f509429232db1acc985bf21c`.
The selected project's retained sequence is `[1, 2, 3, 5, 6, 7, 8]`; the gap
belongs to the separately retained project. Existing history validation,
WAL visibility, caller-transaction, malformed-record and output-failure tests
remain in the full maintained run.

## Paired disk receiving

[`tools/benchmark_event_history.py`](../../tools/benchmark_event_history.py)
creates 1,501 native projects with 6,004 total events, including accepted work
parked as unknown and a dependent queued part. The 1,500 unrelated projects
each carry a 4,096-byte synthetic finding. No external work is submitted.

The producer backs the original native records into a disk database, copies
that file, and opens the copy once with the candidate's writable constructor.
The complete ordered project/part/event row digest is identical before and
after this upgrade. Each source then reads its own file in three fresh
processes, alternating the before/after order. Every process opens read-only,
reads and serializes the selected history 20 times, and closes the ledger.
SQLite work diagnostics run separately from that timed section.

Each paired process also launches the actual history CLI from a separate
working directory using an explicit source bootstrap and isolated Python.
All six CLI processes exit zero with empty stderr and produce the same full
newline-terminated report. Every read-only process and CLI preserves its
database's byte identity. The file hashes differ across the upgrade because
the new index occupies storage; the original logical rows and reports agree.

| Measured operation | Predecessor | Candidate |
| --- | ---: | ---: |
| 20 history reads and JSON serializations, median | 12.489 ms | 2.823 ms |
| Read-only open, 20 reads/serializations, close, median | 12.916 ms | 3.064 ms |
| One actual history CLI process, median wall time | 52.777 ms | 61.706 ms |
| Separate SQLite VM work for one history read | 18,218 steps | 228 steps |

The complete-process measurements do **not** establish a standalone CLI latency
improvement. Interpreter startup and shared-runtime variation remain visible;
the demonstrated benefit is reduced database work and repeated native history
receiving on this multi-project fixture. Full validation and serialization of
the selected project's own history still cost time proportional to that history.

The run used CPython 3.12.14 and SQLite 3.53.1 on a shared Linux runtime. Full
source hashes, raw samples, file identities, migration cost, and actual CLI
receipts are in
[`project-history-index-20261012.json`](project-history-index-20261012.json).
No elapsed-time threshold is used as a test gate.

## Reproduce

With the predecessor available in a separate checkout:

```sh
python -B -m unittest discover -s tests -v
python -B tools/benchmark_event_history.py \
  --before /path/to/6303882-predecessor --after . \
  --neighbors 1500 --finding-bytes 4096 --reads 20 --repeats 3 \
  > /tmp/project-history-receiving.json
```

The benchmark uses temporary databases and denies socket operations in its
consumer processes. It records actual new fixture timestamps, so a repeated
run has its own file/report hashes. Each run checks its exact before/after
logical records and reports internally. It changes no workflow or installed
estate database.
