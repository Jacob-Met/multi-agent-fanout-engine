# Withdraw queued work before submission

Use `Ledger.withdraw_queued(project_id, part_id, evidence)` when a caller has decided
that recorded work should never be submitted. The part must still be `queued`,
and its `worker_id`, `task_id`, `route_json` and `artifact_ref` must all be null.
Dependency-blocked queued work can also be withdrawn.

~~~python
ledger.record_plan(plan)
ledger.withdraw_queued(plan.project_id, "build", {
    "source": "request owner",
    "locator": "request:123/withdrawal",
    "finding": "This work is no longer requested before dispatch.",
})
~~~

Evidence must contain nonblank string `source`, `locator` and `finding` fields,
using the existing ledger evidence validation. Extra JSON fields and literal
string contents are retained. The caller supplies and authenticates the decision;
the ledger does not contact the named source or open the locator.

## Durable result

Withdrawal is terminal and unsuccessful. The row uses the existing `failed`
state and retains the exact decision evidence. The distinct `queued_withdrawn`
event stores that evidence directly, rather than claiming a worker failed.
Plan, payload, digest, idempotency key and absent submission/artifact references
are preserved. Only state, evidence and update time change. Later edits to the
caller's evidence dictionary cannot change either stored copy.

The state update and event insertion use the same `BEGIN IMMEDIATE` transaction
as existing transitions. A failed event write rolls back the state change.
An existing caller-owned transaction is refused by SQLite without being committed
or rolled back by this method.

No new state or schema migration is introduced. Existing dispatchers skip failed
parts, and unfinished descendants remain queued with unmet prerequisites. Existing
inspection reports include the failed count and retained evidence; event history
shows `queued_withdrawn`. A failed count alone does not distinguish withdrawal
from a verified task failure: read the evidence and event history.

## Admission and refusal

Withdrawal succeeds only while the recorded state is queued and all four
submission/artifact references are null. Any non-null reference, including an
empty string, refuses unchanged. Unknown projects/parts, repeated withdrawals,
invalid evidence and all other states also refuse unchanged.

Dispatch admission and withdrawal serialize through SQLite's write transaction.
If withdrawal commits first, later dispatch admission refuses before an adapter
submission. A dispatcher that had already read queued readiness may therefore
raise `LedgerError`; its caller can inspect the current state. If dispatch
admission wins first, withdrawal refuses and preserves the in-flight identity.
The method does not undo a prior admission or clear retained references.

This API does not cancel or terminate running work, contact a worker, establish
that an external effect stopped, or authenticate manually edited ledger rows.
A queued row with null references is the local admission boundary. Keep
`mark_failed` for a verified terminal result of accepted running work, and the
unknown-outcome reconciliation path for ambiguous acceptance/results. See
[task results](task-results.md).

There is no resume or retry transition for withdrawn work. Changing the recorded
plan or recycling a withdrawn part's identity is outside this contract.

## Run the local example

From a source checkout with Python 3.10+:

~~~sh
python -B examples/withdraw_queue.py
python -B -O examples/withdraw_queue.py
~~~

The example uses a private temporary SQLite file, closes and reopens it, then
calls the ordinary dispatcher with a local fake adapter. Its JSON shows no
submissions, one failed withdrawn root, a queued blocked descendant, and the
single `queued_withdrawn` part event. The temporary directory is removed when
the example finishes. It does not invoke a provider, service or external worker.

The focused maintained tests are:

~~~sh
python -B -m unittest discover -s tests -p test_queued_withdrawal_b3d7b32e.py -v
~~~
