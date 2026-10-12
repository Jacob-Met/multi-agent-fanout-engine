# Compare a revised draft with its saved plan

When `Ledger.record_plan` refuses an edited plan under an existing project ID,
compare the draft directly with the plan retained in that ledger:

```sh
python -m fanout_engine.compare_retained --database work.sqlite3 --project source-review --after revised.json
```

The command opens the selected existing ledger through `Ledger.open_readonly`,
validates the complete project through the native inspector, and compares that
saved plan with the revised JSON file. It prints one complete JSON report. It
does not record the revised plan, change task states, reserve work or contact a
Hub. The same command works from an installed package or the repository root
with Python 3.10 or newer and the standard library.

## What the report shows

The main fields are those of [plan comparison](compare-plans.md): full before
and after plans and digests, additions and removals, changed fields and
declaration order, and every before/after native idempotency key. The `before`
plan comes from the saved project; it is not another draft supplied by the
caller.

An additional `retained` section provides the saved `project_id`, `plan_digest`,
`state_counts`, and ordered `part_states` rows with `part_id` and `state`. Those
states and the before plan are from the same inspected SQL snapshot. Existing
`dispatching` and `outcome_unknown` rows remain in those states. The report
provides no evidence about external execution beyond the stored values and is
not a reservation for a later operation.

For example, changing only a draft's instruction changes the complete plan
digest and all its retained native keys, including keys for unchanged parts.
The report may also show that some affected parts are already completed or
have uncertain outcomes. It makes that conflict visible; it does not choose a
replacement project identity, migrate saved rows or decide whether a task can
be submitted again.

Direct native construction can preserve repeated tags and declaration order.
The saved before side preserves that exact representation and its digest.
The candidate JSON side uses the established `Plan.from_dict` normalization,
which sorts and deduplicates input tags. An apparent tag-only difference can
therefore be a real native identity difference between the retained constructor
form and the candidate parser form.

`input_sha256.after` is the SHA-256 of the exact candidate bytes captured by the
CLI. The native helper omits this field. There is no `before` file hash: a live
SQLite view may include committed WAL contents, so hashing only its database
file would not identify the saved snapshot. Use `before.plan_digest` for the
validated native plan identity. Later writers may change the ledger after the
snapshot has been read.

## Native integration

```python
from fanout_engine import Ledger, Part, Plan
from fanout_engine.compare_retained import compare_retained_plan

candidate = Plan("source-review", (
    Part("research", "Read the source."),
    Part("draft", "Write a draft with citations.", ("research",)),
))
with Ledger.open_readonly("work.sqlite3") as ledger:
    report = compare_retained_plan(ledger, "source-review", candidate)
print(report["changed_parts"])
print(report["retained"]["part_states"])
```

The helper reuses the native inspector rather than reading only the project
header. A missing part, mismatched saved key or malformed saved payload refuses
the complete report. No partial comparison is returned for an inconsistent
project. The helper does not take ownership of the supplied Ledger connection.

## Inputs, limits and exits

Paths are literal filesystem names, including spaces and URI punctuation. The
database must already be a regular SQLite file; the command does not create a
missing database, initialize a foreign schema or repair corruption. SQLite's
ordinary locking and committed WAL visibility apply, without immutable-file
assumptions. A candidate must be a regular UTF-8 JSON file of at most 1 MiB.
Both compared plans support at most 256 parts; the final report supports at most
4 MiB, including retained states. The native inspector's existing saved-project
reading behavior is unchanged.

| Exit | Meaning |
| --- | --- |
| 0 | One complete comparison was written. |
| 1 | The output stream failed; it may have received a prefix. |
| 2 | Invalid input, inconsistent or unreadable ledger, comparison limit, or usage error. No success report is written. |
| 3 | The selected project is absent from an otherwise readable ledger. |

To save the result, redirect to a fresh file:

```sh
python -m fanout_engine.compare_retained --database work.sqlite3 --project source-review --after revised.json > comparison.json
```

Shell redirection follows ordinary replacement rules. Do not redirect to either
input or to an existing SQLite sidecar. The command itself opens inputs only
for reading; it does not control what the invoking shell opens first.

## Verification

```sh
python -m unittest discover -s tests -p 'test_compare_retained.py' -v
```

The tests use authored temporary ledgers and draft files. They exercise the
actual CLI from a separate working directory, the motivating record refusal,
exact saved constructor identity, native comparison parity, repeated reads,
closed/reopened storage, uncertain and in-flight states, a committed WAL view
with an uncommitted writer, corrupted late rows, missing inputs and projects,
comparison bounds and output-stream failure. This qualifies the offline
reference consumer; it does not establish an installed estate deployment or a
remote task result.
