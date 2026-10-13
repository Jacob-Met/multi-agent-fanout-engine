# Worker identities at dispatch admission

The caller's `worker_for(part)` callback chooses the worker identity for each
ready queued part. The same identity reaches `Hub.submit` and is retained in
the native SQLite part row and `dispatch_started` event.

A worker identity must be text with at least one non-whitespace character, and
the complete text must encode as UTF-8. `Ledger.mark_dispatching` raises
`LedgerError` before opening its transition when the identity fails that check.
The ordinary `dispatch_ready` path therefore does not call the adapter for that
part. Integers, booleans, bytes, containers, empty/whitespace-only strings and
lone Unicode surrogates cannot become a recorded worker assignment.

Accepted text is retained exactly. Spaces around an identifier, Unicode, case
and other existing characters are not trimmed, normalized or rewritten.
Validation uses the built-in string operations, so a string subclass cannot
substitute a successful whitespace or encoding check. This is an input-shape
check, not a worker registry lookup or an authorization decision; the caller and
adapter still own the meaning of a worker ID.

## Correct an invalid assignment

Select an actual configured worker and retry the same plan through the existing
dispatch entry point:

```python
from fanout_engine import dispatch_ready

report = dispatch_ready(
    plan, ledger, hub, router,
    worker_for=lambda part: "local-worker",
)
```

A rejected assignment leaves that part queued, with no new dispatch event or
adapter call for it. Initial plan recording can already have happened. If an
earlier part was accepted before a later worker selector returned an invalid ID,
that earlier part stays running with its original task and worker identity.
Correcting the selector and calling `dispatch_ready` again skips that accepted
part and can submit the remaining queued ready parts.

The gate is also present on direct `Ledger.mark_dispatching` calls. It does
not revise old ledger rows, change route selection, retry an unknown submission,
or alter task/artifact reference policies. The adapter may still reject a
well-formed but unknown worker through its existing outcome handling.

## Native verification

From the repository root, the standard-library regression commands are:

```sh
python -B -m unittest discover -s tests -p test_worker_identity.py -v
python -B -O -m unittest discover -s tests -p test_worker_identity.py -v
```

The tests use real in-memory and temporary-file SQLite ledgers with a local
recording adapter. They check rejected direct transitions, no adapter call for
invalid assignments, correction without replay of an accepted part, and exact
literal retention in the adapter, part row and event. Valid disk-backed ledgers
are reopened through the actual `python -m fanout_engine.inspect` CLI; complete
database bytes remain unchanged by inspection. No provider or real worker is
contacted.

On the original dca36bef09f39a2b339cc116051b5784619f71ee source, native dispatch
accepted a whitespace-only worker and an integer worker. The adapter received
integer `7`, while SQLite retained the worker as string `"7"`. The unchanged
focused test module records 15 failed and 13 error subcases on that source.
The repaired source passes all four test methods on Python 3.14.4 in normal and
optimized execution. The optimized parent tests run their inspector subprocess
with the ordinary Python flags shown in the test; the inspector source is unchanged.

The ledger binds an ordinary `str` containing the exact accepted characters.
A string subclass cannot substitute different stored text through SQLite's
`__conform__` hook. The dispatch adapter still receives the original object
returned by `worker_for`.
