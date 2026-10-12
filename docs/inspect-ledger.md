# Inspect an existing ledger

Use the retained project's own stored plan, part states and evidence to decide
what to investigate next:

```sh
python -m fanout_engine.inspect --database "work/dispatch.sqlite3" --project sample
```

The command requires Python 3.10+ and this package. Run it from the repository
root or from an environment where the package is installed. `--database` is an
ordinary filesystem path, interpreted relative to the current directory when
relative. Quote names containing spaces or shell punctuation. Literal `#`, `?`,
`%`, `&`, spaces and Unicode are encoded as path data before opening SQLite;
they cannot supply URI options. Symlinks use normal filesystem semantics.

The selected path must already be a regular file. The command opens it using
SQLite `mode=ro`, without schema creation, migration, recovery transitions or
PRAGMA changes. A missing file or parent is not created. An empty, foreign or
corrupt database is refused rather than initialized. This is a reader for the
existing native ledger schema, not a general database browser.

## What the report means

Successful stdout is the complete `inspect_project` report as canonical UTF-8
JSON followed by one newline. It retains the native project ID and digest,
authored part order, instructions, repeated tags, dependency order, all six state
counts, task/worker references, routes, evidence, artifact references and stored
update times. No extra observation time or filename is added to the native
report.

`queued_ready_ids` contains only queued parts whose direct prerequisites are
completed. `blocked_queued_ids` contains the other queued parts. Each part's
`unmet_dependencies` identifies its direct unfinished prerequisites and their
observed states. `dispatching` remains `dispatching`; `outcome_unknown` remains
unknown. A report does not reserve work, verify an external artifact or prove
that an ambiguous submission was accepted. It never invokes a Hub, submits a
task, retries work or authorizes replay.

The existing inspector reads the selected plan and all its part rows in one SQL
statement, then validates the complete captured data before any successful
output. Invalid later rows cannot produce a partial successful report. This
consumer loads the whole selected project; it adds no fixed project-size cap.

## Exit statuses and output

| Status | Meaning |
| --- | --- |
| `0` | The complete report was written and flushed. |
| `1` | Report output failed; the receiving stream may contain a prefix. |
| `2` | Invalid command options, unreadable database, incompatible schema, or inconsistent stored records. No report is written. |
| `3` | The database was readable but the exact project ID was not present. No report is written. |

Diagnostics go to stderr. Missing projects use `project_not_found`; the native
inspector's `missing_parts` and `invalid_record` codes remain visible. Ordinary
SQLite errors such as missing tables, corrupt files or lock timeouts are shown
as database-read failures. Normal interpreter and operating-system termination
remain outside these controlled statuses.

To format the JSON for reading, use the standard-library formatter and check
both commands' exit statuses if a shell pipeline is used:

```sh
python -m fanout_engine.inspect --database "work/dispatch.sqlite3" --project sample > report.json
python -m json.tool report.json
```

Shell redirection follows the shell's normal file replacement rules. The command
does not create an output file itself. Prefer a fresh report filename.

## Read-only scope and active writers

The connection cannot change ledger rows and performs no schema initialization.
It uses SQLite's normal read-only locking, including visible committed WAL
records. It does not set `immutable=1`, which would be inappropriate for a
potentially active ledger. Uncommitted changes from another connection are not
part of the observed report. A later invocation can therefore report newer
committed state.

SQLite may create or modify WAL shared-memory bookkeeping where the filesystem
permits it. Read-only here is a database-content guarantee, not a promise that
every directory entry, access time or shared-memory byte remains unchanged.
The regular-file check is not protection against a concurrent path replacement.
Use the ledger owner's authorized stable path. This command neither copies an
active database nor chooses a snapshot/custody policy for its owner.

Python callers can use the same opening path:

```python
from fanout_engine import Ledger, inspect_project

with Ledger.open_readonly("work/dispatch.sqlite3") as ledger:
    report = inspect_project(ledger, "sample")
    print(report["queued_ready_ids"])
```

Mutation methods on that connection fail with SQLite's read-only error. The
ordinary `Ledger(...)` constructor retains its existing initialization behavior.

## Try a complete disk example

Create a fresh authored database, then inspect that already existing file:

```sh
python examples/create_retained_ledger.py sample.sqlite3
python -m fanout_engine.inspect --database sample.sqlite3 --project sample
```

The sample creator refuses an existing destination. It creates seven durable
parts covering all six native states. Only `notes` is queued and ready;
`publish` is queued with `draft` running and `verify` unknown. `acknowledge`
remains dispatching. The evidence and task references are explicitly authored
examples; no remote worker is called.

For the API recipe, replace `work/dispatch.sqlite3` in the Python example above
with `sample.sqlite3`. Both receiving paths read the same preexisting database.
