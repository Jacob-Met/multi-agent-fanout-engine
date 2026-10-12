# Ledger rollback after a failed operation

The ledger now rolls back when `COMMIT` fails, extending its existing cleanup
for body errors and cancellation. The original exception propagates; the
operation is not retried automatically. A caller may inspect the same connection
or retry a safe local recording operation after addressing the cause.

At source `546ad359eacb94a43efad8148457c709bb792fe7`, cancellation in the body
already rolls back correctly. However, a failed SQLite `COMMIT` leaves the
transaction open because commit runs outside that cleanup block. Later ordinary
ledger reads enter the connection's context manager, which can commit those
leftover writes. A failed `record_plan` can consequently become durable after
the caller has already received its error. The failed operation also retains a
writer reservation until it is committed or rolled back.

The cleanup now covers both the body and commit, preserving existing rollback
for `KeyboardInterrupt`, `SystemExit`, `GeneratorExit`, and
`asyncio.CancelledError`. `BEGIN IMMEDIATE` remains outside
that block: if beginning an operation fails because the caller already owns a
transaction, the failed operation does not roll back the caller's prior work.
The helper still does not support nested ledger write operations.

## Verification

Run the focused receiving tests or the full suite:

```sh
python -B -m unittest discover -s tests -p test_transaction_rollback.py -v
python -B -m unittest discover -s tests -v
```

The focused tests use temporary, real SQLite databases. A separate read
connection blocks commit while the writer's busy timeout is zero, producing a
real `database is locked` error after writes have been admitted. Other cases
raise cancellation after an event has been inserted. The tests then exercise
ordinary ledger reads and an independent database connection, verify unchanged
rows/events, and check safe subsequent writes. They also preserve a caller-owned
transaction when `BEGIN` refuses and exercise a successful durable lifecycle
with idempotent plan/running acknowledgements.

The original source at `546ad359eacb94a43efad8148457c709bb792fe7` retains writes
after failed commit; the corrected source leaves neither pending nor durable
rows from that failed operation. Existing dispatch, inspection, preview,
routing, schema, state names and event formats are unchanged.

This is local transaction cleanup, not crash recovery or a guarantee that an
already committed operation can be undone. Database rollback can itself fail,
and external Hub effects are outside the SQLite transaction. The existing
unknown-outcome and reconciliation rules still apply to ambiguous remote work.
