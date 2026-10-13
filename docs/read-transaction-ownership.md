# Ledger reads preserve the caller's transaction

The public `Ledger.part_state`, `part`, `idempotency_key`, `completed_ids`,
`dispatchable_ids` and `events` helpers read from the current connection without
committing or rolling back its transaction. An explicit read snapshot stays open
until its caller ends it. A pending write remains pending, including when a read
raises its ordinary missing-row, JSON-decoding or SQLite error.

When no explicit transaction is active, these helpers keep their existing
autocommit reads. They return the same values, use the same SQL and retain the
same exception types. The change does not add an arbitrary-write or transaction
management API. Callers using the connection directly remain responsible for
their own transaction lifetime.

## Why the connection context was removed

At original main `23daeba5b97ea87733f95bae19b45525e40ae95c`, the six helpers
entered `with self._db`. Python's SQLite connection context completes an active
transaction on exit: it commits on success and rolls back on failure. It does
not merely scope a read.

A real file-backed example starts a caller transaction and changes a fictional
note from `before` to `pending`. Calling any of the six original readers ends the
transaction and makes `pending` visible to an independent connection. Reading a
missing part instead ends the transaction and restores `before`. With this
correction the reader leaves that choice to the caller.

The error cases matter too. The original `part` JSON-decoding failure rolls
back pending work, whereas the original `events` helper commits before decoding
its already-fetched rows. Both corrected helpers propagate their existing error
without completing the surrounding transaction.

## Native verification

Use the maintained regression module:

```sh
python -B -m unittest discover -s tests -p test_read_transaction_ownership.py -v
python -B -m unittest discover -s tests -q
```

The seven focused test methods use disposable SQLite files and fictional
records. They cover every helper and both event-query forms, independent
connection visibility, explicit caller commit and rollback, missing-part
errors, invalid retained JSON, failed SQL and ordinary autocommit reads. A WAL
control uses the actual read-only opener: another connection commits a new
state while the original reader retains its older explicit snapshot, then the
reader sees the new state after its own rollback.

On Linux x86-64, CPython 3.14.4:

- The unchanged original suite passes 179 tests.
- The seven new methods on the original source produce 15 failing subcases and
  one error. The extra error follows an invalid event record made durable by
  the original reader; ordinary autocommit controls pass.
- The corrected complete suite passes all 186 tests in ordinary execution and
  all 186 under `python -O`.
- `git diff --check` passes.

This is a local SQLite qualification. It does not exercise an external Hub,
provider or installed worker service. The existing write-transaction helper,
schema, lifecycle rules, query projections and workflow files are unchanged.
