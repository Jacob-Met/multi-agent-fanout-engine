# Retain an accepted task identity

`Ledger.mark_running(project_id, part_id, task_id)` records the task identifier
returned after an adapter accepts work. The identifier must be nonblank text
that can be encoded as UTF-8. An empty string, whitespace-only text, a nonstring
value or an unpaired Unicode surrogate raises `LedgerError` before any SQL.
The part and its recorded events remain unchanged.

Accepted text is retained exactly, including surrounding whitespace, Unicode,
embedded newlines and NUL characters. A `str` subclass is accepted according to
its literal characters. Its truthiness, whitespace, encoding, string-conversion,
equality and SQLite adaptation overrides cannot replace those characters or
control admission. The stored `task_id` and the `dispatch_accepted` event contain
the same plain string.

```python
ledger.mark_running("sample", "build", "  worker-task-雪\t")
```

The part must already be `dispatching`. Repeating the call for an already
`running` part with the same literal identifier remains idempotent: it adds no
event and does not update the row. A different identifier cannot replace the
accepted one. Existing state-transition and transaction-rollback rules apply.

## Adapter acceptance and uncertainty

`dispatch_ready` validates a returned task receipt before asking the ledger to
record it. The ledger also enforces the identity boundary for direct callers and
before SQLite binding. If a returned receipt is refused after adapter submission,
the existing dispatcher parks the part as `outcome_unknown`. It does not replay
the submission; independent ready parts can still proceed. A valid receipt whose
string subclass is falsey or provides a SQLite adaptation hook retains its literal
text and can become `running` normally.

The identity is a locator supplied by the adapter. Retaining it does not verify
remote execution or a terminal result. Completion and evidence-based
reconciliation retain their separate requirements.

## Focused regression

```sh
python -B -m unittest discover -s tests -p test_task_identity.py -v
python -B -O -m unittest discover -s tests -p test_task_identity.py -v
python -B -m unittest discover -s tests -q
```

The five regression methods cover admission before SQL, row/event preservation,
literal identity through read-only inspection and history in fresh processes,
idempotence, equality and SQLite adaptation overrides, dependent blocking,
independent continuation and no repeated adapter calls. The CLI subprocesses
inherit optimized mode when the tests run under `-O`.
