# Record a verified task result

After an adapter returns an accepted task identifier, a part is `running`.
When the authorized caller receives a verified terminal result, it can record
that result directly:

```python
ledger.mark_completed(project_id, part_id, artifact_ref, evidence)
ledger.mark_failed(project_id, part_id, evidence)
```

`mark_failed` requires an existing running part and a dictionary with nonblank
string `source`, `locator` and `finding` fields. Record what the receiving worker
or service actually reported. For example:

```python
ledger.mark_failed("sample", "build", {
    "source": "accepted worker result",
    "locator": "worker-result:build-17",
    "finding": "The completed build process returned exit status 2.",
})
```

The ledger stores the evidence, marks the part `failed`, updates its recorded
timestamp and appends one `failed` event in one existing SQLite transaction.
Original task, worker, route, payload and idempotency identities remain intact.
Mutating the caller's evidence dictionary after the call cannot change the saved
record. A persistence failure propagates through the existing rollback behavior.

The transition refuses queued, dispatching, unknown, completed and already-failed
parts, preserving their records and events. Repeating a failure call does not
append another event or replace the retained evidence. A caller that is unsure
whether an earlier local write completed should first inspect the saved ledger.

Failed parts stay ineligible for submission. Their queued dependents remain
blocked, while independent ready parts retain their ordinary dispatch behavior.
The operation does not call an adapter, retry or cancel external work, or open an
evidence locator. The caller remains responsible for establishing that evidence
belongs to the accepted task and proves a terminal failure.

If acceptance or the outcome is uncertain, keep the existing
`mark_outcome_unknown` and evidence-backed `reconcile_unknown` workflow. A timeout
or disconnected polling call by itself is not a verified terminal failure.

## Local executable example

```sh
python examples/failure_flow.py
```

This launches one authored local Python child that writes a fixture diagnostic
and exits with status 7. The caller observes the completed child, records its
failure, and asks the dispatcher for ready work again. The JSON shows one child
submission, a retained `failed` build, the blocked `verify` part, and the direct
failure event. All work uses an in-memory ledger and the local reference adapter.

## Focused regression

```sh
python -m unittest discover -s tests -p test_direct_failure.py -v
python -m unittest discover -s tests -v
```

The new cases cover SQLite reopen and exact identity retention, dependency
blocking with independent dispatch and no replay, all other native state
refusals, invalid evidence, missing identifiers, and a real SQLite trigger
refusal followed by recovery. Existing transaction and reconciliation tests
retain their own scope.
