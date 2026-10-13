# Explain queued dependency blockers

The native inspector records which direct prerequisites remain incomplete.
A long queued chain can hide the running, unknown, failed, dispatching, or
ready queued work at its far end. The blocker report follows that chain and
shows which queued parts each stopping point currently holds.

```sh
python -m fanout_engine.blockers --database work/dispatch.sqlite3 --project sample
python -m fanout_engine.blockers --database work/dispatch.sqlite3 --project sample --output new-blockers.json
```

If the project ID is not known, discover it in the selected ledger first:

```sh
python -m fanout_engine.projects --database work/dispatch.sqlite3
```

Pass the returned `project_id` unchanged to `--project`. The accepted
[project catalog](project-catalog.md) validates saved plan identities; the blocker
command then validates the complete selected project's retained state.

Use the existing open ledger in Python:

```python
from fanout_engine.blockers import inspect_blockers

report = inspect_blockers(ledger, "sample")
for blocker in report["frontier"]:
    print(blocker["id"], blocker["state"], blocker["blocked_queued_ids"])
```

## Where traversal stops

A frontier is the set of distinct unfinished parts reached by following a
blocked queued part's incomplete prerequisites through other queued parts.

| Recorded prerequisite | Report behavior |
| --- | --- |
| Completed | Stop this path; it contributes no blocker. |
| Queued with incomplete prerequisites | Follow those prerequisites. |
| Queued with all prerequisites completed | Include this ready queued part. |
| Dispatching, running, outcome_unknown, or failed | Include this exact part and state; do not look through it. |

The last rule preserves what is already recorded. Even if a running part has an
incomplete prerequisite in retained history, the report stops at that running
part. A completed intermediate part also cuts off older unfinished ancestors.
This follows current dependency eligibility instead of reconstructing or
repairing past execution.

For example, with `source → draft → review` all queued, `source` is the
frontier for both `draft` and `review`. If `draft` is already running,
`review` is held by `draft`; the report does not look through running work.
A diamond that reaches the same frontier through two queued paths counts each
downstream queued part once.

These are observations from one validated retained snapshot. Ready queued work
is not a reservation or a claim that its worker or route is available. Failed
or unknown work does not become retryable. No task is dispatched, reconciled,
recovered, reprioritized, or reclassified.

## Report

| Field | Meaning |
| --- | --- |
| `schema_version` | `1`. |
| `project_id`, `plan_digest` | Exact validated native plan identity. |
| `queued_ready_ids` | All currently queued parts with completed direct prerequisites. |
| `blocked_queued` | One row per blocked queued part: its ID, direct unmet IDs, and distinct frontier IDs. |
| `frontier` | Only frontier parts reached from blocked queued work, with exact state, retained worker/task references, and affected queued IDs. |

Rows, frontier IDs, ready IDs, and affected queued IDs follow the native plan's
declaration order. `direct_unmet_ids` retains the original dependency order.
Unused ready or nonqueued work is absent from `frontier`. A project without
blocked queued work has empty `blocked_queued` and `frontier` lists.

Worker and task references remain stored labels; this command does not open or
authenticate them. Returned lists are detached from the ledger. Traversal is
iterative and memoized, so a valid deep dependency chain does not require a
larger Python recursion limit.

## Reads, errors, and files

The Python helper calls the existing `inspect_project` exactly once. That
inspector validates the complete native project and reads its plan and part
rows in one SQL statement. Malformed unrelated rows are still rejected before
any report is returned. Its existing identity and error contract is unchanged.

The CLI reuses `Ledger.open_readonly` for an existing SQLite file, the native
UTF-8 JSON encoder, the shared SQLite destination check, and the existing
create-only report writer. It does not initialize missing databases. Normal
SQLite locking and WAL visibility still apply; a read-only connection is not an immutable database-file snapshot.

| Exit code | Meaning |
| --- | --- |
| 0 | Complete report written to stdout or a new output file. |
| 1 | Output failed, including an already existing destination. |
| 2 | Invalid usage, unreadable database, or invalid retained data. |
| 3 | Project not found in the selected ledger. |

An error while writing stdout can leave a partial stream. The command preserves
existing output files, and validates and encodes the complete report before
publishing a new file. See [the existing-ledger guide](inspect-ledger.md) for
the shared read-only and export boundaries.

The selected database and its `-wal`, `-shm`, and `-journal` names remain
reserved even when the sidecars do not yet exist. The shared check covers the
selected and resolved database names, existing hard-link aliases, and conservative
case and Unicode-normalization variants. It runs after complete record validation
and encoding, before creating any report. Unrelated sidecar-looking names remain
available. Existing output files still cannot be replaced.

The blocker command reuses the shared inspection guard and the owner's original
black-box path cases from [PR #58](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/58).
The guard was introduced at `943ae6fb9d1bd661392cf6e7fe6640430e3ca5cb` and
accepted unchanged in main at `6d76703f8a3d5a29e56bf9fab97523935b06e61c`.
This composition preserves the accepted project catalog and Ledger implementation;
it adds no separate catalog or storage reader.

## Tests

```sh
python -m unittest discover -s tests -p 'test_blockers*.py' -v
```

The tests exercise real local SQLite ledgers, mixed states, shared dependencies,
completed and in-flight cutoffs, declaration order, deep graphs, detached
results, one-query/no-write inspection, and the native CLI. All data and state
transitions in the tests are authored local fixtures; they make no external
worker or model call.
