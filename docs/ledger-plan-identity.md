# Record a plan with a consistent identity

`Ledger.record_plan(plan)` captures a standard `Plan` with native `Part` and
`Plan` constructors before opening a write transaction. Its captured digest must equal
the identity produced when the supplied plan was validated. The project JSON,
part payloads and idempotency keys are then recorded from that same capture.

This matters for the historically admitted mutable Part-like objects. Previously,
an edit after validation could record new instructions with an old digest and
keys. The stored project would then fail the native inspector's consistency
checks. A caller-side edit during persistence could also make the project JSON
and later part rows disagree.

## Admission and compatibility

An unchanged native plan retains its declaration order, dependency order and
repeated direct-constructor tags. The capture does not use `Plan.from_dict`
normalization. The caller's plan and original part objects remain untouched.

If a changed source still forms a valid plan but has a different identity,
recording raises `LedgerError("plan has changed since validation")`. Invalid
captured fields are rejected by native Plan validation. Both refusals occur
before a write transaction, including when the same project is already present.

The existing return values remain the same: the first record returns `True`;
recording the same validated identity again returns `False` without adding
events. A newly validated plan with a different digest is still refused when
that project already has another recorded plan. An intentional source edit
therefore needs a newly constructed Plan and the existing project-identity
rules still apply.

Custom `Plan` subclasses retain their existing serialization and idempotency-key
methods. The native capture applies only to the standard `Plan` class; a custom
implementation remains responsible for its own identity and mutable-input
contract. Converting a subclass to a standard Plan could silently replace its
key namespace or discard a valid custom document order.

Because `dispatch_ready` calls `record_plan` before selecting workers or
submitting parts, an already-stale standard Plan is refused before those callbacks.
This change concerns ledger admission and the data recorded from its capture.
It does not change callback behavior after `record_plan` returns or repair
previously inconsistent stored projects; the native inspector continues to
report inconsistent retained data.

## Verify

```sh
python -m unittest discover -s tests -p test_ledger_plan_identity.py -v
python -m unittest discover -s tests -v
```

The focused course checks disk reopening and exact native identity, edited
sources before new and repeated records, invalid captured fields, caller edits
during a real SQLite transaction, unchanged retained database bytes, and stale
entry through the dispatcher with a local test-only adapter. Compatibility
controls reopen custom key namespaces and custom document order from disk.
