# Transaction-preserving state-query composition

The current ledger combines the read-transaction correction from [PR #50](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/50) with the state-only query from [PR #26](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/26). Both contributions keep their original source, tests and qualification records. This note describes their combined behavior.

## Current behavior

`part_state`, `part`, `idempotency_key`, `completed_ids`, `dispatchable_ids` and `events` do not enter the SQLite connection context manager. Calling these read methods therefore does not explicitly commit or roll back a caller-owned transaction. Successful reads and the existing missing-part errors leave its pending changes available to the caller, who can choose to commit or roll back. A read-only connection can retain its explicit snapshot.

`part_state` also selects only `state` using the existing project/part key. It returns the same state string and raises the same `LedgerError("part is not in the ledger")` when the row is absent. It does not decode or copy the retained payload and evidence columns. The other five methods retain their existing SQL, JSON decoding, results and ordering.

The write transaction helper, schema, transitions, event formats and the accepted worker-identity validation remain unchanged. This composition adds no nested-write support, retry, dispatch or reconciliation operation. Native SQLite errors may themselves abort a transaction; this is a correction to the read helpers' explicit transaction management, not a guarantee against every database-engine failure.

## Exact source inputs

| Input | Commit |
| --- | --- |
| Receiving main, including PR #52 worker-identity admission | `c86113dd09ff17d0c606b390b693caddb967f8b1` |
| PR #50 read-transaction owner | `a321ed405f49ada08e390a2fc094698374214848` |
| PR #26 state-query owner | `6611a828ca5a8cf05b2b7f52450323e6c9f06e40` |

The combined `fanout_engine/ledger.py` is 16,805 UTF-8 bytes, Git blob `8d1a3d87e0b58d1eae9f7308da247f01b0d65af2`, SHA-256 `2d58cb4a792ca00790f8a4197af0fd54eb92ff6573dbd8900c7ec51e9fa449a9`. It is the receiving main with the six reviewed connection contexts removed, the read-ownership comment retained, and PR #26's exact `part_state` query/error body outside that context. No other existing main file changes.

The two owner test modules and their four documentation/evidence files are carried unchanged. In particular, the state-projection timing record remains the original owner's recorded measurement; it is not a new timing result for this composition.

## Reading the historical guides

[PR #26's qualification](qualification/state-projection-20261012/README.md) describes its original isolated change as retaining the connection context. [PR #50's guide](read-transaction-ownership.md) describes its isolated correction as retaining the original query shapes. Those statements belong to their pinned source versions. The combined version removes the read contexts and uses the state-only projection described above. The original guides and measurements are preserved rather than silently rewritten as evidence for a different source.

## Independent receiving

A second worker froze its real-SQLite receiver and original results before this composition or the PR #50 candidate was received. The unchanged receiver exercises all six successful read methods and the existing missing-part errors from `part_state`, `part` and `idempotency_key`.

| Source received with the same nine-case oracle | Transaction-preservation cases passing |
| --- | --- |
| Original main `23daeba5b97ea87733f95bae19b45525e40ae95c` | 0 / 9 |
| PR #50 owner source | 9 / 9 |
| PR #50 + PR #26 on the original main | 9 / 9 |
| Current composition retaining PR #52 | 9 / 9 |

On the original, every successful read commits a caller's pending marker so that a second SQLite connection can see it. Each missing-part error rolls the pending marker back. On the accepted composition, reads preserve the caller's open transaction and pending value, the second connection still sees the committed prior state, and the caller's explicit rollback restores that state.

Two independent source reviews also checked the complete composition. One compared all bytes with a separately constructed expected result. The other compared parsed Python ASTs and checked the accepted worker-identity method and all nine other production modules remain unchanged.

The complete maintained suite passes **193 tests, zero failures, zero errors and zero skips** on native Linux / CPython 3.14.4. This includes both owners' regression modules, real WAL snapshot checks, missing-row and malformed-record behavior, all six native part states, project scoping, dispatch eligibility and the accepted worker-identity cases. All 64 Python source files retained their hashes through that run. The earlier composition on the previous main passed its then-current 189 tests; those results are retained separately.

The [composition receipt](qualification/ledger-read-composition-20261013/receiving.json) records source and evidence hashes, including the unchanged independent receiver and original negative results. Full native output remains separately retained; the published receipt contains no operator-specific working directory or private endpoint.

## Reproduce

From a checkout containing this composition:

```sh
python -B -m unittest discover -s tests -p test_read_transaction_ownership.py -v
python -B -m unittest discover -s tests -p test_part_state.py -v
python -B -m unittest discover -s tests -v
```

These tests use synthetic plans, local adapters and disposable SQLite files. This integration does not claim an installed production worker, external provider execution, a new cross-platform qualification, or a new performance measurement. Hosted Actions remain unrun under the standing no-Actions instruction; the only workflow is unchanged and publication uses GitHub's supported skip directives for its push/pull-request events.
