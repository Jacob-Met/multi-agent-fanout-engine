# Ledger plan identity receiving

The corrected source preserves one validated native identity through
`Ledger.record_plan` admission and persistence, while retaining custom Plan
serialization and idempotency-key behavior.

## Frozen source

| Item | Identity |
| --- | --- |
| Original main | `dca36bef09f39a2b339cc116051b5784619f71ee` |
| Reviewed remote source commit | `85166e291e6862249a942e5596d60a1be1f27211` |
| Executed local source commit | `82816fffa823a605f1d54d4bbc091c2a26447afb` |
| Complete source tree shared by both commits | `9f71912fbec8a35a89c8ac843c29c073a0e2a7be` |
| Corrected ledger SHA-256 | `2ad8ad98de472a8deeaf6b0e656e868b906cbdc855912374aa456998797e5b14` |
| Unchanged Plan dependency SHA-256 | `884f85eff1ef526a8a47e6ee258fc473ce6647e914bd93298d91824640deab61` |

The executed local commit and published remote commit have different commit
metadata and the same complete Git tree. The evidence commit adds only this
directory; production source and maintained tests retain their reviewed bytes.

## Independent acceptance

Reviewer `hamon_implementation` independently inspected the corrected source and
authored the retained [receiving driver](independent/receive_ledger.py).
On macOS with CPython 3.13.7, the driver passed **52 explicit checks in normal
Python** and **52 in genuine optimized Python**, with no failures.

The course compares original and candidate source directly. It verifies native
and combined custom-subclass serialization/key behavior, exact persisted
identity after read-only reopening, idempotent re-recording, unchanged database
bytes/events, repeated tags and dependency order. It reproduces the original
stale-admission digest mismatch and the original part-payload mismatch from a
real SQLite BEGIN callback. The corrected source refuses stale native input
before BEGIN and persists one detached identity during the callback.

The [normal receipt](independent/normal.json) and
[optimized receipt](independent/optimized.json) retain the runtime, immutable
source pins, observations, check count, and source-preservation guards.

| Retained file | Bytes | SHA-256 |
| --- | ---: | --- |
| `independent/receive_ledger.py` | 9721 | `fc7ecfb02daf0feb20ccfd09d145f97696fd74059f158c671775df50716ab203` |
| `independent/normal.json` | 1428 | `f891c282f00b14c563bd7221da351c1897444751b31e76ce7f1fdeb9c00ccebf` |
| `independent/optimized.json` | 1428 | `6e2afe048b5beb767740a2ad85df963cd1979b0176b709438e67bb7e7de47d4f` |

The driver is the exact executed historical file, including its original local
checkout path and local commit pin. It creates a fresh course directory, so it
is not a path-independent rerun wrapper. The maintained regression module is
the portable repository entry point:

```sh
python -m unittest discover -s tests -p test_ledger_plan_identity.py -v
python -O -m unittest discover -s tests -p test_ledger_plan_identity.py -v
```

The author ran all eight corrected regression methods successfully in both
modes. The earlier six-method draft also ran the full 185-method suite with four
existing macOS `/dev/full` skips; that full-suite result is historical and does
not constitute a new full-suite run of the corrected source.

## Limits

This evidence covers standard Plan admission and persistence plus preservation
of the existing subclass protocol. It does not qualify caller mutation during
dispatch callbacks after `record_plan` returns, repair existing inconsistent
ledgers, or establish installed-worker/provider adoption.

[Behavior guide](../../ledger-plan-identity.md) ·
[Maintained regression module](../../../tests/test_ledger_plan_identity.py)
