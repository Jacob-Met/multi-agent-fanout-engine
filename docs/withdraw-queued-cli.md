# Withdraw one queued part from an existing ledger

Use this operator command when a caller has decided that one authored part is no
longer requested and it has not been submitted. It calls the native
`Ledger.withdraw_queued` transition once, using an explicitly selected existing
ledger, project, part and evidence:

```sh
python -m fanout_engine.withdraw \
  --database ./work.sqlite3 \
  --project local-request \
  --part build \
  --source "caller decision" \
  --locator "request:local-request/decision-2" \
  --finding "The caller no longer requests this work."
```

The project and part must already exist. Replace these example identifiers with
the exact recorded identifiers. The command treats the database argument as a
literal filesystem path, including characters that have special meaning in a
SQLite URI. It opens with SQLite `mode=rw`, which refuses a missing database at
connection time. It does not initialize, migrate or repair a schema.

Before changing the selected part, the command runs native project inspection.
This checks the retained plan and part identities and required columns. The
transition then rechecks queued state and the absence of worker, task, route and
artifact references in its existing write transaction. A blocked queued part is
eligible too. A running, dispatching, completed, failed or outcome-unknown part
is refused. The command has no batch mode, resume operation or external worker
termination behavior.

## Evidence and committed state

All three evidence arguments must be nonblank. Their literal strings, including
Unicode and surrounding whitespace, are retained; the locator is not opened.
The existing transaction changes only the selected row's state, evidence and
update time, and adds one `queued_withdrawn` event with that same evidence.
Identity, payload, idempotency key and other parts stay unchanged.

The terminal state is `failed`, meaning unsuccessful terminal work. The distinct
event records a caller's withdrawal of unsubmitted work, not a verified running
task failure. Dependents remain blocked. Existing dispatchers exclude the
withdrawn part. Repeating the command refuses the terminal state without another
event. There is no new schema or state.

After commit the command emits one UTF-8 canonical JSON object followed by a
newline. It contains exactly `project_id`, `part_id`, `state`, `event` and
`evidence`:

```json
{"event":"queued_withdrawn","evidence":{"finding":"The caller no longer requests this work.","locator":"request:local-request/decision-2","source":"caller decision"},"part_id":"build","project_id":"local-request","state":"failed"}
```

Confirmation encoding is checked before opening the database. Output delivery
happens after the committed transaction and cannot undo it.

| Exit | Meaning |
| --- | --- |
| 0 | Withdrawal committed and confirmation was written. |
| 2 | Usage, database, native inspection, evidence or transition refused. No successful withdrawal was committed by this command. |
| 1 | Withdrawal committed, but confirmation output failed. The diagnostic explicitly says it committed. |

For exit 1, inspect the retained state and history before retrying:

```sh
python -m fanout_engine.inspect --database ./work.sqlite3 --project local-request
python -m fanout_engine.history --database ./work.sqlite3 --project local-request
```

This is an ordinary SQLite writer with normal locking and WAL visibility. Native
inspection precedes the transition; it is not authentication of a manually
modified database or a guarantee against arbitrary out-of-band edits. The native
transition retains its atomic state/reference recheck. Evidence and confirmation
do not imply that any external task was stopped.

## Existing-file API

`Ledger.open_existing(path)` provides the schema-free existing-file writer used
by this command. It enables foreign keys and closes the connection if setup
fails. Like `Ledger.open_readonly`, it accepts a literal filesystem path rather
than a caller-supplied URI. The factory itself does not validate a whole schema;
the command performs native inspection before its single transition. Use the
existing `Ledger(...)` constructor when deliberately creating a new ledger.
