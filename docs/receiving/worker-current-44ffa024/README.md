# Worker identity receiving with the current ledger

This composes the existing supplemental receiving from [PR53](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/53) with main `afd0ac5657888cb348be8717bb3c8ac436a29dfd`, tree `1cbfce6bc068f73281640ca4181a7c14d536abb7`. The prior contribution head `6adf88a6ecc51203b16c73f24caf2a72ca30b298` remains the second parent of the proposed ordinary fast-forward branch update.

## Source scope

Main has since adopted ledger initialization cleanup, state projection and caller-owned read transactions. The worker admission guard, write transaction, running transition and read-only open routine remain byte-identical to the previously qualified base; the supplemental receiver consumes the changed part/state/dispatchable read methods.

This contribution makes no production-code change. The five-method `tests/test_worker_identity_receiving.py` remains exact published blob `5085f395f75e9da6d3956a7235635e591e11bc5d`. The README adds its existing worker-identity guide row to the current table, preserving all other current README content. Main's worker identity implementation, guide, tests, accepted read/initialization changes and prior evidence retain their source identities.

## Native receiving

The five bounded courses ran on verified MSI with Python 3.14.3 and SQLite 3.50.4, Windows 11 build 26200. All adapters and inputs are authored local fixtures. The existing interpreter was used directly; nothing was installed.

| Course | Methods passed | Failures/errors/skips |
| --- | ---: | ---: |
| `test_worker_identity.py` | 4 | 0 |
| `test_worker_identity_receiving.py` | 5 | 0 |
| `test_read_transaction_ownership.py` | 7 | 0 |
| `test_part_state.py` | 3 | 0 |
| `test_ledger_init_cleanup.py` | 2 | 0 |
| **Total** | **21** | **0** |

The current main worker course includes eight exact valid identities, actual inspector CLI reopen of disk-backed SQLite files and byte-preserving read-only inspection. The unchanged supplemental course adds zero-SQL admission refusal, subclass override resistance, no adapter call on invalid selection, literal identity reopening, dependency readiness and preservation of a prior accepted part. The current read/state/init courses verify explicit transaction ownership, retained snapshots, project scope, current state visibility and failed-constructor cleanup.

All 18 received original files match their canonical Git blobs. All 18 original and 19 candidate source files were verified before and after execution, with no bytecode files or extra candidate source files. The task-owned temporary directory was empty afterward. The source directories are received snapshots, not Git checkouts.

## Receiver continuation and custody

The first course's Python subprocess exited 0 with four passing methods. The initial orchestration process 116836 then exited 1 because its report check expected Unix LF around `OK`, whereas Windows emitted CRLF. The raw successful output, original runner and first progress receipt's hash were retained. The progress file itself was subsequently updated as the continuation recorded later courses. The continuation normalizes only the report comparison and verifies those already completed four methods without rerunning them. It then runs the remaining 17 methods against the unchanged source. Continuation process 132632 completed with exit 0.

The native command timestamps span 2026-10-13T03:48:25.774113Z through 2026-10-13T03:49:54.583841Z, including the receiver correction interval. All five actual test subprocesses exited 0.

- [candidate-receipt.json](candidate-receipt.json): exact native receipt, SHA-256 `478a1b8ee118a380247a9e7a60631cef094039408c1fdb38ab3851f43f943ac3`.
- [course.log](course.log): labeled concatenation of the ten exact stdout/stderr byte streams, with all 21 method results.
- [initial-receiver-attempt.json](initial-receiver-attempt.json): the preserved orchestration-only stop and the first successful test result's progress hash.

Complete source packet, both runners, original/candidate sources and individual log streams remain at `C:\HAMON\acceptance\fanout-worker-current-44ffa024`. Published receipt and log files preserve their exact native bytes, including Windows line endings where present.

## Repeat

From the composed repository root, using its supported Python interpreter:

```sh
python -B -m unittest discover -s tests -p test_worker_identity.py -v
python -B -m unittest discover -s tests -p test_worker_identity_receiving.py -v
python -B -m unittest discover -s tests -p test_read_transaction_ownership.py -v
python -B -m unittest discover -s tests -p test_part_state.py -v
python -B -m unittest discover -s tests -p test_ledger_init_cleanup.py -v
```

## Limits

This is candidate-only current-dependency receiving. The historical original-defect witness and 188-method full suite were not repeated; their earlier Linux receipts remain separate evidence. These 21 methods do not claim the entire current repository suite, all supported Python/OS combinations, live provider calls or real worker execution. Main and other owner branches remain unchanged. No workflow source change or Actions run is part of this contribution.
