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
or service actually reported. Required fields must contain nonblank UTF-8 text.
The ledger checks the literal Unicode contents using the built-in string
operations, so a string subclass's overridden validation methods cannot invent
a nonblank field or reject an otherwise valid field. Accepted surrounding
whitespace, Unicode and additional JSON evidence fields are preserved.

The same required-field checks apply to `mark_outcome_unknown` and
`reconcile_unknown`, and to `mark_completed` when evidence is supplied.
Invalid required text raises `LedgerError` before a transaction or state/event
write. Direct completion still permits omitted evidence. These checks establish
usable recorded text; the caller remains responsible for verifying its claims.

For example:

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

To retain the same real local-child result for a separate receiving process,
choose a **new** SQLite file in an existing directory:

```sh
python examples/failure_flow.py --database failed-example.sqlite3
python -m fanout_engine.inspect --database failed-example.sqlite3 --project local-failure-demo
```

This mode closes the writing connection and reopens the saved ledger read-only
before printing its events and project state. The ordinary inspector can then
read the same failed build, exact evidence and blocked `verify` part. The full
example JSON still includes the child's stdout, stderr and exit code. The
ledger retains the existing task evidence and timeline, rather than this
example-specific report envelope.

An existing file, directory or symlink is refused unchanged. The example does
not create missing parent directories. Unknown options and incomplete arguments
are rejected before a ledger is created or a child is started; `--help` describes
the command without running it. Omitting `--database` retains the in-memory
behavior and existing JSON result shape.

Exit 0 means the example recorded and printed the expected failure successfully;
the demonstration child itself deliberately exits 7. Argument, persistence or
output errors return 2, and a caught keyboard interruption returns 130. Once a
new database has been created, it is retained if a later step fails. The error
message names that file so it can be inspected: it may contain an accepted task
without a recorded terminal result. No successful result is claimed on that
path, and retrying the same filename refuses rather than rerunning the child.
If the example is interrupted while its child is still running, it terminates
and collects that local example child before returning. This cleanup is limited
to the child started by this invocation.

## Focused regression

```sh
python -m unittest discover -s tests -p test_direct_failure.py -v
python -m unittest discover -s tests -p test_evidence_text.py -v
python -m unittest discover -s tests -p test_failure_flow_retained.py -v
python -m unittest discover -s tests -v
```

The new cases cover SQLite reopen and exact identity retention, dependency
blocking with independent dispatch and no replay, all other native state
refusals, invalid evidence, missing identifiers, and a real SQLite trigger
refusal followed by recovery. Existing transaction and reconciliation tests
retain their own scope.
