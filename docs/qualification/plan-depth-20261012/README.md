# Dependency-depth repair: author qualification

## Source and change

Original source: `Jacob-Met/multi-agent-fanout-engine` main commit
`49f042cf8652860aae3e8bf8d90a47641f2d6527`, tree
`dcebecc57e533a02b293ffeb64c4757c6b614e9b`.

Only the cycle traversal in `fanout_engine/plan.py` changes. An explicit stack
replaces recursive calls while retaining depth-first dependency order, completed
and active visitation sets, and the existing cycle error. It does not reorder
parts or dependencies, alter plan serialization/digests, raise Python's recursion
limit, or change the preview consumer's 256-part limit.

| File | Original Git blob | Qualified Git blob |
| --- | --- | --- |
| `fanout_engine/plan.py` | `8967c1db75507f564852c66ed913aa55103f6f76` | `734c5619ba0241882703e6f5fd2ebe34632f0bc2` |
| `tests/test_plan_depth.py` | absent | `be83941ff56ad72564234f6b177d4bddf64f0107` |

## Reproduced behavior

The original core passes its 44 maintained tests. With Python's unchanged
recursion limit of 1,000, the new depth tests reproduce four errors:

- A valid 2,500-part dependency chain declared before its prerequisites raises
  `RecursionError` instead of constructing a native plan.
- A 2,500-part cycle raises `RecursionError` instead of the documented native
  `PlanError("dependency graph contains a cycle")`.
- A separate cycle following a valid 1,500-part chain is never reached before
  the traversal raises `RecursionError`.
- The 1,500-part plan-to-ledger-to-inspector test fails at plan construction.

The first four tests were written and run against the original production
source before its repair. A fifth shared-prerequisite/disconnected-component
positive control was then added and also run against the original source.
The complete focused original result is one passing method and four errors.

## Candidate verification

Author runtime: local Linux, Python 3.12.14, unchanged recursion limit 1,000.
The materialized closure contains 20 original runtime, test, example, package,
workflow and selected documentation files; every original byte sequence was
checked against its Git blob identity. Historical qualification packets were
not materialized. This is not represented as a complete repository checkout.

```sh
python3 -m unittest discover -s tests -v
python3 examples/demo.py
python3 examples/inspect_plan.py
```

The repaired candidate passes all 49 tests. Both unchanged examples exit 0.
The depth suite verifies the deep valid plan's declared order, direct dependency
readiness and unchanged recursion setting; the original cycle error on deep and
disconnected cycles; a 1,500-part stored-plan inspection; and shared ancestors
that must remain acyclic.

These are author qualification results for the source blobs above. Independent
receiving, any other Python version, source integration, remote adapter execution
and installed deployment are separate outcomes. No hosted workflow was run for
this qualification and no workflow file or repository setting changed.
