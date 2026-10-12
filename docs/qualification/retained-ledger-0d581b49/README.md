# Existing-ledger inspection receiving — 2026-10-12

This increment exposes the accepted native project inspector through a real
read-only database opener and CLI. The original source at
`0317b4bc80638a8e952857aa5966b0e20d1fab72` has neither `Ledger.open_readonly` nor
`fanout_engine.inspect`; an original-source CLI invocation exits 1 with
`No module named fanout_engine.inspect`. The new 13-method suite records the
same absent capability before implementation: 15 failed assertions/subcases and
two missing-method errors. These failures are absence witnesses, not evidence of
an existing installed-ledger incident.

## Source boundary

The product delta adds one pathlib import and an alternative `Ledger` opener,
one new CLI module, a new test module, a new sample creator, a usage guide and an
appended README example. The old inspector, transaction helper, dispatch loop,
Plan/routing behavior and existing tests retain their source bytes.

While receiving proceeded, current main advanced to
`5ce9a6f472f9217d4c294777645d4ace420b5ab8` through the separately owned dispatch
eligibility improvement. The six-file contribution composes without changing
that incoming source or its tests/evidence. Transaction-commit recovery in PR14
remains with its owner; this increment does not adopt its pending source.
The complete composed suite passes all 86 maintained tests in 3.293 seconds;
all six independently reviewed files retain their exact SHA-256 values.

## Author receiving

On CPython 3.12.14 / SQLite 3.53.1, all 13 new tests and the original 69 tests pass
on the inspected parent, for 82 maintained methods. The focused tests use actual
SQLite files and real CLI processes, including a live WAL writer with one
committed update and a second uncommitted update. They cover literal URI
punctuation and Unicode paths, relative paths/symlinks, no schema initialization,
no file/parent creation, foreign/corrupt/empty databases, missing projects,
missing rows, malformed late evidence, mutation refusal and `/dev/full` output
failure. No native test is replaced by a fake successful report.

`author-receipt.json` retains the separate disk-sample exercise. A new seven-part
database is created once, then read independently through the CLI and Python API.
Both outputs match at 3,540 bytes. Only `notes` is queued and ready, `publish`
remains blocked, and all six states survive. The database's SHA-256 remains
`f26b4047bba2878d7c37f680a59e46e03fb7a85d96b52292b6f329e29b42bbff` after both
reads and the refused repeated sample creation. A closed output pipe returns 1
with one diagnostic and no shutdown traceback.

## Independent root receiving

The parent reviewer independently read all six product/test/guide files and
authored a separate SQLite/CLI receiver. It performs 19 checks and six CLI
processes in each of normal and genuine optimized Python. It hand-checks ordered
states/readiness, repeated tags, literal filename identity, direct DELETE
refusal followed by readable reuse, committed WAL visibility with a writer's
transaction left open, unchanged WAL bytes, late malformed evidence refusal,
missing-file no-create, empty-database no-initialization, and distinct absent
project status. All 19 checks pass in each mode.

The complete receiver and raw normal/optimized results are in `independent/`.
Re-run it from a checkout with an explicit source root:

```sh
python docs/qualification/retained-ledger-0d581b49/independent/receive_readonly.py .
python -O docs/qualification/retained-ledger-0d581b49/independent/receive_readonly.py .
```

The independent review pins:

| File | SHA-256 |
| --- | --- |
| `fanout_engine/ledger.py` | `3ff1caaff8957291ba14c4dd02cbcd26146e422db95adcca606718357792122a` |
| `fanout_engine/inspect.py` | `83c3f11be76640c3d074ababefa6d2380d9c6489beac0235e88c341a5c86ca2f` |

## Limits and publication

The test environment is Linux; this receiving does not claim a native Windows
or macOS run. The package requires Python 3.10+, but no new hosted version matrix
was run. The unchanged sole GitHub workflow listens only to push/pull_request;
publication and integration commits carry `[skip ci] [skip actions]` under the
standing no-Actions direction. No workflow/settings change or remote worker
invocation is part of the increment.

Read-only refers to ledger content. SQLite's ordinary WAL shared-memory
bookkeeping, access times and later concurrent commits remain possible. No
`immutable=1` assumption or protection against a concurrent path replacement is
claimed. A successful report is a retained observation, never replay permission.
