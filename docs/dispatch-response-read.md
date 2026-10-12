# Unreadable dispatch acknowledgements

`Hub.submit` may return any mapping with a non-empty string `task_id`. Reading
that mapping is part of the acknowledgement boundary: a deferred mapping can
raise after `submit` has returned, before the dispatcher can establish a task
reference.

The dispatcher records ordinary exceptions from task-ID extraction or validation
as `outcome_unknown`, using the part's existing idempotency key as the evidence
locator. Its finding includes the exception class, without the exception message
or response payload. It then continues the other independent ready parts in the
same call. An unknown prerequisite still blocks its dependents.

The uncertain part is never automatically submitted again. Resolve it through
the existing `reconcile_unknown` operation only after obtaining external evidence.
Ordinary mappings and accepted task identifiers retain their original behavior;
leading or trailing whitespace in an otherwise non-empty identifier is preserved.
Missing, empty and non-string identifiers retain their existing unknown-state
finding.

`KeyboardInterrupt`, `SystemExit` and other `BaseException` interruptions still
propagate. They leave the already admitted part in `dispatching`, for the existing
restart-recovery operation to park as unknown. If writing the unknown result to
SQLite fails, that database exception also propagates. This change neither proves
remote acceptance nor guarantees local persistence when the database is failing.

## Reproduce and verify locally

Run from the repository root with Python 3.10 or later:

```sh
python -B -m unittest discover -s tests -p test_dispatch_response_read.py -v
python -B -m unittest discover -s tests -v
python -O -B -m unittest discover -s tests -v
```

The six response-read regression methods use only local adapters and temporary
SQLite databases. They cover an ordinary deferred `Mapping`, a failing custom
`get`, a failing string validator, malformed-response controls, exact accepted
identifier preservation, cancellation/recovery, and an injected persistence
failure. The disk-backed case closes and reopens the database, verifies the
retained unknown state and evidence, confirms no repeated submission, reconciles
from authored local evidence, and then dispatches the previously blocked dependent.

### Qualification on 2026-10-12

The original source was fetched at commit
`0b169f9df939350911d76dbda88023fe37ee53bf`. All 28 selected source, test, example,
manifest and workflow files were checked against their Git blob identities; the
complete repository tree contained no `AGENTS.md`.

On that original source, a mapping that raises `OSError` when its task identifier
is read aborts the dispatch call. The first part stays `dispatching` across a
database reopen, while an independent second part stays queued. A later pass
starts the second part but cannot classify the first. The new regression module
retains four original error cases; its ordinary and cancellation controls pass.

On CPython 3.12.14/Linux, all 96 original methods passed before the change. With
the response guard and six new methods, all 102 methods pass in both ordinary
and genuine optimized Python, with no skips. The tested dispatcher has SHA-256
`a2a558913a46e5b279c2a2f0370bd5ba16cd4a55058fbbb07fa58cff29ca38f5`.

An independent worker reviewed that exact source and used a different local
consumer: it committed an acceptance receipt to SQLite, then returned a mapping
backed by the closed receipt connection. The original dispatcher raised
`ProgrammingError`, retained `dispatching`, and left the independent part queued.
The candidate persisted the unknown finding, started the independent part,
reopened without repeating either submission, and released the dependent only
after explicit receipt reconciliation.

These are source-level, local-adapter results. No installed worker, model
provider, remote acknowledgement service or hosted Actions matrix was exercised.
