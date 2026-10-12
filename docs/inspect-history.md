# Inspect recorded event history

Use the retained ledger's timeline to see what it recorded before a part reached
its current state:

```sh
python -m fanout_engine.history --database "work/dispatch.sqlite3" --project sample
python -m fanout_engine.history --database "work/dispatch.sqlite3" --project sample --part verify
python -m fanout_engine.history --database "work/dispatch.sqlite3" --project sample --output new-history.json
```

The command requires Python 3.10+ and this package. Run it from the repository
root or an environment where the package is installed. The database must be an
existing regular file. It uses the same literal-path, SQLite `mode=ro` opening
boundary as the [current-state inspector](inspect-ledger.md). It does not create
or initialize a missing, empty or incompatible database.

## What the timeline contains

Successful output is canonical UTF-8 JSON followed by one newline, either
on stdout or in the explicitly selected new `--output` file:

| Field | Meaning |
| --- | --- |
| `schema_version` | `1` for this report format. |
| `project_id` | The exact stored project identifier. |
| `plan_digest` | The validated identity of its recorded native plan. |
| `part_id` | The exact selected part, or `null` for the whole project. |
| `events` | The selected recorded events in ascending `seq` order. |

Every event retains the native `seq`, `project_id`, `part_id`, `event`,
`detail_json` and `at` fields. `detail_json` keeps the stored JSON text exactly;
the additional `detail` field contains its parsed JSON value for ordinary
consumers. Names, references, details and timestamps are not rewritten. A whole
project timeline includes project-level records such as `plan_recorded`, whose
`part_id` is `null`.

`--part` matches one exact, case-sensitive identifier in the stored plan and
includes only events with that part identifier, matching the existing
`Ledger.events(project_id, part_id)` selection. It excludes project-level
records. A known part that has never produced an event returns a successful empty
`events` list; an unknown part returns `part_not_found` and status 3.

Sequence numbers represent ledger recording order. They are global to the
database, so another project's events can leave gaps in a selected timeline.
Wall-clock timestamps may run backwards; they do not determine report order.
Recorded details do not establish external execution order or independently
prove a provider result. The command does not infer absent events, reconstruct
missing history, retry a submission, reconcile work, or change a part's state.

## Validation and read-only behavior

One compound SQL statement captures the stored plan header and all retained
event rows for the project. The native plan identity, positive increasing event
sequences, known part references, event names, finite timestamps and strict finite
UTF-8 JSON details are validated before any successful report. The entire
captured project history is checked before applying `--part`; malformed events
for another part still refuse the report. Unknown nonempty event names and
finite JSON detail shapes remain readable, without being interpreted as state
transitions.

This is a report of retained rows, not a proof that every historical event is
present. It does not validate the current part-state table or claim that retained
events reconstruct those states. Use the existing current-state inspector for
that separate observation. Both commands can observe later commits on later
invocations.

With `--output`, the CLI validates and encodes the complete report before
creating a temporary file beside the requested destination. It flushes and
syncs that file, then publishes it with an exclusive hard link: an existing
file, directory or symlink destination is never replaced. An absent parent or
failed publication returns status 1, leaves the existing destination intact,
and may leave a staging file if cleanup itself fails. Without `--output`,
stdout behavior is unchanged. This is a new-file delivery operation, not a
crash-durable multi-file transaction.

The CLI performs no database-content writes. Normal SQLite locking and committed
WAL visibility apply, and uncommitted changes from another connection are not
included. SQLite may update shared-memory bookkeeping as described in the
current-state guide. The command loads the whole project's retained event history;
it does not impose a new history-size limit or provide paging.

Python callers can supply an existing open `Ledger`:

```python
from fanout_engine import Ledger
from fanout_engine.history import inspect_history

with Ledger.open_readonly("work/dispatch.sqlite3") as ledger:
    report = inspect_history(ledger, "sample", part_id="verify")
    for event in report["events"]:
        print(event["seq"], event["event"], event["detail"])
```

The helper returns detached values. It does not start, commit or roll back a
caller's existing transaction, and may observe that connection's own pending
changes. Missing project/part and invalid record failures use `InspectionError`;
ordinary database errors propagate to Python callers.

## Exit statuses and a local example

| Status | Meaning |
| --- | --- |
| `0` | The complete selected report was written and flushed. |
| `1` | Report output failed; stdout may contain a prefix, or file publication failed. |
| `2` | Invalid options, unreadable/incompatible database, or invalid retained records. No report is written. |
| `3` | The exact project or part is absent. No report is written. |

Diagnostics go to stderr. Use `--output` for exclusive new-file publication
instead of shell redirection, whose ordinary rules may replace a file.
Interpreter and operating-system termination remain outside these controlled
statuses.

The existing example creator provides a complete local input:

```sh
python examples/create_retained_ledger.py sample.sqlite3
python -m fanout_engine.history --database sample.sqlite3 --project sample
python -m fanout_engine.history --database sample.sqlite3 --project sample --part verify
python -m fanout_engine.history --database sample.sqlite3 --project sample --output new-history.json
```

The creator refuses an existing destination. Its references and event findings
are authored fixtures; this example does not contact a Hub or remote worker.

Run the history consumer regressions with:

```sh
python -m unittest discover -s tests -p test_history.py -v
```
