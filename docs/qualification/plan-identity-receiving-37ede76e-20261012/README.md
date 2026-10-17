# Plan identity receiving

This branch retains an independently authored dispatcher regression module and
native receiving evidence for the estate's preview, ledger and dispatch identity
repairs. PR49's production source remains unchanged in this branch. The
ledger/dispatch combination was reconstructed in a separate isolated checkout.

## Frozen sources

| Boundary | Exact source commit | Production blob |
| --- | --- | --- |
| Corrected preview, PR44 | `02ab6b6705705b9738a0f7d6601dee0d35b9efc7` | `71dabb931a1adafd7ff449b53d3a1223e08e290d` |
| Corrected ledger, PR48 | `85166e291e6862249a942e5596d60a1be1f27211` | `627ece1c327b6a15eb47f25b3e7041c371e4d558` |
| Dispatcher, PR49 | `842d33b92ac5fc2be186e7172535e83c2ca3a6de` | `bec8a82063dc06653128f155b8487428847b73c2` |

The [independent dispatcher module](../../../tests/test_dispatch_plan_identity.py)
was first published as the only added file at
`d2eff21ec16ad98c67194a18f3c86a3427b7199d`, with complete tree
`94ea316923682a22fb32625c407aa732fb4e629b`. Its blob is
`c429fb2105be4f0e2c76b5879371212f4a736243`, SHA-256
`dfb894387879ea273014f48c4d4cc0e2003ace0dbc53e0f0524194e3b6004cd2`.
The remote tree equals the native tested tree, whose local commit is
`f3647f3901caaa4b422ec8217d0f1daea1f7a05e`.

## Native results

All courses below ran on macOS with CPython 3.13.7. These are focused receiving
results; they do not claim another whole-suite run.

| Course | Normal | Optimized |
| --- | --- | --- |
| Six independent dispatch methods against original `23daeba5` | Two stale-entry failures, six callback errors; stable/custom controls pass | Not run |
| Same six methods against exact PR49 | 6/6 pass | 6/6 pass |
| Exact corrected PR48 plus PR49, both identity modules | 14/14 pass | 14/14 pass |
| Four earlier independent preview methods against corrected PR44 | 4/4 pass | Not rerun |

The dispatcher course mutates caller-owned fields during route-Mapping reads,
worker selection, route selection, Hub acceptance, Hub timeout and receipt
reading. It checks exact submitted payloads, independently derived keys,
accepted/unknown bookkeeping, blocked dependencies, no repeated submission,
read-only disk reopening and preserved database bytes. The compatibility case
combines a custom Plan's readiness, document order and key namespace.

The paired ledger/dispatch course uses PR48's unchanged eight identity methods
and the six dispatcher methods. Its machine-readable receipt pins both product
sources, both test modules and the unchanged Plan/routing dependencies. All
source hashes remain exact after both modes. This qualifies that two-increment
combination, including the common stale-input error contract.

## Separate independent callback acceptance

The shared-delivery reviewer inspected the exact original and PR49 package
sources, then ran a separately authored public-API checker with explicit checks
that remain active under `-O`. Each candidate mode passes **307/307 checks across
12 scenarios**. Each original mode reproduces **93 failed checks out of 231**,
with exit code 1; both candidate modes exit 0. Original failures and all four
raw stdout/stderr streams are retained in the receipt.

The scenarios edit current, later-ready and blocked caller sources during
worker, router, Hub and response callbacks, with accepted and ambiguous replies.
They also cover explicit-route Mapping conversion, repeated-dispatch parking,
mixed and all-native object identity, combined custom Plan readiness/document/
key policies, and stale-input rejection before ledger admission. The checker
confirms all 20 source files and its own bytes are preserved. The complete module
AST outside PR49's single admission insertion matches the original source.

The archived runner preserves the original native scratch paths and admission
metadata assumptions; it is an exact historical driver. The checker accepts an
archived source-root argument and can be used separately. The raw receipt embeds
the full source-admission manifest. Its original input bytes are now retained
separately as `independent/source-admission.json`; this additive closure changes
no source, checker, runner or executed receipt. No installed-worker or provider call was made
by this receiving course, and it does not claim another composition or full-suite
run.

| Retained file | Bytes | SHA-256 |
| --- | ---: | --- |
| [independent/source-admission.json](independent/source-admission.json) | 5724 | `a0222b7056132a58411092ba4c8908103f40c1f7e3b7195ddfaf20b4c111db7b` |
| [independent/check_dispatch_callbacks.py](independent/check_dispatch_callbacks.py) | 17828 | `d48aa3aefda6a64a3b5db635748e8d9c3ef88d02fe04423f287b977fdbde9975` |
| [independent/run_dispatch_receiving.py](independent/run_dispatch_receiving.py) | 4915 | `6827444d6925e56a05437b09f6d7f4f1278f21c96d0eaaa9e9301db3d6db09a3` |
| [independent/dispatch-independent-receipt.json](independent/dispatch-independent-receipt.json) | 444674 | `76be8d72e3456ffa8236dfa83c688a4db6164ab8bb9580076e261b79c2aab2ce` |

## Corrected preview source acceptance

The preview review reads the corrected source, tests and guide. Removing its
single standard-Plan type guard around capture yields a complete module AST
identical to the previously approved `20be9f145d` version. A separately authored
custom Plan combining reversed document order, namespaced keys and restricted
readiness produces the exact original report on the corrected source. The
first draft reproduces a PreviewError for that same valid custom Plan.

The unchanged earlier four-method native course passes on the corrected source.
The exact current source is accepted in
[PR44's review comment](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/44#issuecomment-6134948354).
The earlier course source remains at
[53207122 / test_preview_plan_identity.py](https://github.com/Jacob-Met/multi-agent-fanout-engine/blob/53207122bb3c90d69e41651f7b7d544d70770180/tests/test_preview_plan_identity.py).

## Retained bytes

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| [dispatch/original-focused.txt](dispatch/original-focused.txt) | 15939 | `d05f39da0992463853d5772eccd47d017c4e4d64c3c2b541a8acac80915928ad` |
| [dispatch/normal.txt](dispatch/normal.txt) | 1190 | `8707a8543d87b40c37b66b0cfeb19a99af2d1f687e542455c00b06017cad2b3d` |
| [dispatch/optimized.txt](dispatch/optimized.txt) | 1190 | `754b046476f033221935603a10a221887f22472587c7cfbdaf0899c26cc861ac` |
| [ledger-dispatch/receiving.json](ledger-dispatch/receiving.json) | 1835 | `c43d149ada01618294fc1e085cea738bbc636484ea48cc7c60065ff11c57e6bf` |
| [ledger-dispatch/normal.txt](ledger-dispatch/normal.txt) | 2605 | `be77c975e1a103a5d39bf0cbb66ff76b600ca16067c3d244d6e3b45ea76d8e17` |
| [ledger-dispatch/optimized.txt](ledger-dispatch/optimized.txt) | 2605 | `a63c34bb97b2bb51fc1ee8fd15ad6d3849141899384b5ac0d15c1accaa785289` |
| [preview/corrected-source-review.json](preview/corrected-source-review.json) | 1019 | `5ee40d5902c7a351b4c37fbb8063137a6e1589421b27b74515cd412f2a2e4996` |
| [preview/focused.txt](preview/focused.txt) | 840 | `f96b62c625989831c997bc5ed0ede045437f00f72f913b06a33a116ac2586a45` |

The logs and JSON receipts are copied byte-for-byte from the executed native
courses; their original absolute paths describe those historical runs. The
portable dispatcher course in this checkout runs with:

```sh
python -m unittest discover -s tests -p test_dispatch_plan_identity.py -v
python -O -m unittest discover -s tests -p test_dispatch_plan_identity.py -v
```

To repeat the paired course in an isolated checkout of the test commit, use
`fanout_engine/ledger.py` and `tests/test_ledger_plan_identity.py` from the pinned
corrected ledger commit, then discover `test_*_plan_identity.py` in both modes.

These local courses do not establish installed-worker or provider adoption.
Source owners retain their PRs and the main-branch integration decision.
