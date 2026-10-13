# Close a connection after Ledger setup fails

A failed `Ledger` constructor must release the SQLite connection that it acquired. This integrates the existing correction from [PR #42](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/42), retaining the original contributor's source and tests.

## Behavior

After connecting, the constructor sets the row factory, enables foreign keys and initializes the existing schema inside a cleanup boundary. If any setup step raises, including an interruption derived from `BaseException`, it closes the acquired connection and re-raises. Connection refusal itself still propagates directly. Successful construction leaves the connection available until the caller closes the ledger.

Schema initialization remains nontransactional. Closing a failed constructor does not undo earlier committed schema statements or repair an incompatible database. The correction does not change schemas, read transaction ownership, state-query projection, worker identity admission or other Ledger methods. It does not address unrelated test-fixture resource warnings or add handling for a failure of `close()` itself.

## Source and existing review

The original owner is commit `dd03fd1f9a2e9d80032b5ae226412552b66162c2`. Its complete `__init__` body and test module are retained exactly. The current candidate was composed on accepted main `cb30577caedeb2d722abf74047b42407d0c7f995`, preserving the reviewed read-transaction/state-query integration, exact-source receiving utility, comparison exporter and preview-guide correction.

The composed `fanout_engine/ledger.py` is 16,975 bytes, blob `c7cbd46e260b964b1a8a62eb425ae4e2861ddd4f`, SHA-256 `a346c8408db6b6a92a88b894ece6c605fa0e1099f3cf4a2ae4578a937c02d463`. All ledger source outside the initializer remains the accepted version. The original test blob is `e8455bff8e26d533c39beacd13d05802c46716bd`.

Three earlier independent receiving records already exercised the failure boundary:

- [Linux / Python 3.12 receiving](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/42#issuecomment-6134612914) covered actual corrupt bytes, incompatible schema, database lock and interruption, plus retained consumers.
- [Separate initializer review](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/42#issuecomment-6134705544) compared the exact source and closed-handle behavior with frozen original criteria.
- [ThinkPad / Python 3.14 receiving](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/42#issuecomment-6135720593) checked real setup failures, exact handle closure, connection refusal and successful initialization.

Those results remain the earlier reviewers' observations on their stated pins. This integration does not relabel them as new execution or combine their case counts.

## Current composition qualification

The complete maintained suite passes **202 tests, zero failures, errors or skips**, under Linux / CPython 3.14.4. The suite includes the original two initializer regressions and all accepted read-ownership, state-projection and worker-identity tests. All 70 Python source-file hashes remained unchanged through the run. `git diff --check` passed.

The earlier composition on `27502202fe2429eef11740d23a8e760c4a7d9fc5` passed its then-current 195 tests. That separate receipt is retained; after the comparison exporter added seven maintained tests, the current composition was checked again.

The integration receiver also checked that the initializer's parsed AST equals the owner's exact method and that the rest of the ledger AST equals current main. Its [machine-readable receipt](qualification/ledger-init-integration-20261013/receiving.json) preserves source identities, the actual command, output hashes and the limits of this new run.

To run the maintained checks from a checkout containing this correction:

```sh
python -B -m unittest discover -s tests -p test_ledger_init_cleanup.py -v
python -B -m unittest discover -s tests -v
```

The unchanged workflow and repository policy remain in place. Publication retains the standing no-Actions instruction through supported skip directives for the existing push/pull-request workflow. Source adoption does not imply an installed production worker or external service execution.
