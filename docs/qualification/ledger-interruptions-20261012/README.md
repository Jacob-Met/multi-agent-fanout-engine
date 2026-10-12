# Interrupted ledger transaction: author qualification

## Source and repair

Original source: `Jacob-Met/multi-agent-fanout-engine` main commit
`49f042cf8652860aae3e8bf8d90a47641f2d6527`, tree
`dcebecc57e533a02b293ffeb64c4757c6b614e9b`.

The sole production change is `except Exception` to `except BaseException` in
`Ledger._transaction`. An exception raised inside the transaction body now
rolls back even when it is a `KeyboardInterrupt`, `SystemExit` or `GeneratorExit`.
The same exception is re-raised; this change does not turn an interruption into
a successful operation or suppress cancellation.

| File | Original Git blob | Qualified Git blob |
| --- | --- | --- |
| `fanout_engine/ledger.py` | `28e8eeafa37a9faceebddff7de1894cc35fe189b` | `e08c0dd67bde3753179b7ff9cdec9038bb15f64c` |
| `tests/test_ledger_interruptions.py` | absent | `634c717337bb1886cffb18a3b7e665d0cfda5fdd` |

## Original failure

The deterministic fault injection raises an interruption from `time.time` while
the original implementation is constructing its second project-part row. The
project and first part have already been inserted inside the open transaction.
The original exception handler does not roll back a base exception. A later
public `part_state` read enters and exits the connection context, committing the
incomplete project. `inspect_project` then reports `missing_parts` for the second
part. No thread scheduling or remote service is needed to reproduce this state.

The maintained regression file was written and run against unchanged production
source first. Three methods yield five failure observations: incomplete-plan
rollback fails for each of KeyboardInterrupt, SystemExit and GeneratorExit;
interrupted dispatch admission and interrupted acceptance each retain their
uncommitted state change. RuntimeError provides a passing existing-behavior
control.

## Candidate verification

Author runtime: local Linux, Python 3.12.14. The exact 20-file original runtime,
test, example, package, workflow and selected documentation closure was verified
against Git blob identities. Historical qualification packets were not
materialized, so this is not a complete checkout claim.

```sh
python3 -m unittest discover -s tests -v
```

All 47 tests pass. The added tests verify that an interrupted new plan is absent
and can be cleanly recorded afterward; interrupted dispatch admission retains
the complete previous queued record and event history; and interrupted running
acknowledgement retains its previous dispatching record. That in-flight part
remains ineligible for submission and can move through the existing explicit
interruption recovery into `outcome_unknown`.

The injection controls exceptions inside the transaction body. It does not
claim to model process termination, power loss, database corruption, commit-time
uncertainty or failures of rollback itself. Existing SQLite durability and
reconciliation behavior remain separate. These are author results; independent
receiving and source integration are separate outcomes. No hosted workflow,
remote adapter, provider operation or installed deployment was run.

## Independent disk-backed receiving

Root separately authored and ran `receive_interruptions.py` against both
original and candidate source on Python 3.12.14. It raises actual SIGINT after
the SQL event write for each of four operations: plan recording, dispatch
admission, running acknowledgement and completion. It then performs the
ordinary public state read, closes the ledger and reopens the same database.

The original source propagates all four signals but commits each interrupted
change after that read. Both the stored snapshot and event history differ in
all four courses. The candidate propagates all four signals while preserving
both prior values in all four courses. The interrupted acknowledgement also
passes through the existing recovery path to `outcome_unknown` and remains
ineligible for resubmission. Exact outputs are in `interruption-before.json`
and `interruption-after.json` beside the independent receiver.

Run that receiver against an explicit source directory:

```sh
python3 docs/qualification/ledger-interruptions-20261012/receive_interruptions.py .
```

## Composition with the accepted graph repair

The integration parent is now main commit
`7a05c33c63b309425b5904914e9faf589ce7aff7`, tree
`c96135f157822e3de764da2ec10d6963c06330af`. It independently replaced recursive
graph validation with a Kahn traversal. This ledger contribution preserves
that accepted algorithm and all of its new tests, qualification notes and
README additions; it does not carry the separate superseded DFS proposal.

The 22-file current runtime/test closure was checked against original Git blobs.
Current main passes 50 maintained tests; the composed ledger candidate passes
53. The only modified original file remains `fanout_engine/ledger.py`, at the
same qualified blob listed above. Rerunning the separately authored actual-SIGINT
receiver on this parent still reproduces all four original failures and passes
all four candidate courses. The exact results are `current-before.json` and
`current-after.json`.
