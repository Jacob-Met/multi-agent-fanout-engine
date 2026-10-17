# Plan identity composition with the current main branch

This qualification receives the reviewed preview, ledger and dispatcher repairs
together with the worker-identity repair merged through PR52. The source merge
is [`de72b62cac3f2d783691b7dfe39800e658b0800b`](https://github.com/Jacob-Met/multi-agent-fanout-engine/commit/de72b62cac3f2d783691b7dfe39800e658b0800b),
tree `7579c83e1dcc823d59b28bb19090d5d2c8e420a7`. Root retains the
main-branch integration decision.

## Exact source composition

| Ordered parent | Commit |
| --- | --- |
| Main including PR52 | `c86113dd09ff17d0c606b390b693caddb967f8b1` |
| Prior qualified plan-identity composition | `d94e560f85028dca0d8798d16b377f72f562618a` |

Native Git produced the same complete tree and ordered parents at
`e5fc82c3ddb278fa60a01e320fd49bf3d59dd362`, without a merge conflict or
manual source edit. The two commit IDs differ because their commit metadata
differs; the tested source tree and ordered parents are identical.

The prior composition retains preview [PR44](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/44),
ledger [PR48](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/48)
and dispatcher [PR49](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/49)
with their original ownership and exact accepted source. Its original
[pinned-main receiving](../plan-identity-composition-37ede76e-20261013/README.md)
remains intact, including the earlier independent static review and demo.

The new main changed only `Ledger.mark_dispatching`, its worker-identity
guide and its four-method test module. The combined ledger is exactly the
previous accepted ledger text with that one method replaced by its current-main
text. `Ledger.record_plan` remains byte-for-byte equal to the accepted
snapshot repair. This composition preserves both repairs.

| Production file | Exact blob in this source merge |
| --- | --- |
| `fanout_engine/preview.py` | `71dabb931a1adafd7ff449b53d3a1223e08e290d` |
| `fanout_engine/ledger.py` | `01c2f7845cad6f92152f797bbad8f4e791cc7273` |
| `fanout_engine/dispatch.py` | `bec8a82063dc06653128f155b8487428847b73c2` |

The complete source tree has 215 regular files. All 212 other files from the
prior composition remain exact. The two PR52 additions match current main
exactly, and all 180 unrelated files from current main retain their identities.

## Independent static acceptance

The independent reviewer accepted this exact source commit, tree and parent
order. All 19 explicit checks passed. The review reconstructed the entire tree,
verified the complete ledger text against the two accepted method sources,
checked both unchanged production pins, and preserved the precise scope of the
earlier acceptance. The reviewer did not execute another runtime course.

The unchanged review is [independent-composition-review.json](independent-composition-review.json),
Git blob `11c88c62671188d1313a828b7a9704b0f9645e2d`.

## Actual native checks for the new source tree

The following focused courses ran on macOS with CPython 3.13.7 after fetching
the published source and verifying its tree and ordered parents:

| Course | Normal parent | Actual `-O` parent |
| --- | ---: | ---: |
| Maintained plan-identity and native-key methods | 25/25 pass | 25/25 pass |
| Maintained worker-identity methods | 4/4 pass | 4/4 pass |

All four commands exited 0 with no failures, errors or skips. The existing
`python3 -B examples/demo.py` command also exited 0, with empty stderr and
the exact expected dependency output:

```text
accepted research on worker-a at model-a/low
started: research
waiting on prerequisites: write
```

All 215 source files, the executed driver and its original admission input
remained byte-for-byte unchanged.

The focused commands use the unchanged maintained tests:

```sh
python3 -B -m unittest discover -s tests -p 'test_*_plan_*.py' -v
python3 -B -m unittest discover -s tests -p test_worker_identity.py -v
python3 -O -B -m unittest discover -s tests -p 'test_*_plan_*.py' -v
python3 -O -B -m unittest discover -s tests -p test_worker_identity.py -v
```

The worker tests invoke their inspector children with the ordinary flags
encoded in that unchanged test module. The optimized counts describe the
test parents; they do not claim optimized inspector children.

The earlier complete 202-method course applies to source
`b0330ae230d033d6e7d4a56b564180ef7b185092`: 198 passes and four
`/dev/full` skips. It was not repeated for this bounded new-main delta.
The focused courses above address the newly combined worker and plan behavior.
They do not qualify those four skipped methods or a Linux runtime.

## Retained execution and input bytes

The executed driver retains its original native paths and frozen source pins.
`source-admission.json` is the original 215-file manifest consumed by that
driver. `receiving.json` records every actual command, count, exit code, raw
stream identity and the demo output. These are historical execution records.

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| [receive_current_main.py](receive_current_main.py) | 7469 | `01c47e895847f0e964ee3a4da2e3e05d6ab6f23b7e70ffd076b2db9b7e02f3cc` |
| [source-admission.json](source-admission.json) | 61797 | `2586c9138fa714f09de739190a34490d51cd0888c4d80d004679ddd9c11fe51a` |
| [receiving.json](receiving.json) | 5840 | `4b751bd729cff62376350f8011adfa0ddb4d81008397cc8c4bcc0ded99d6d64c` |
| [plan-normal.stdout.txt](plan-normal.stdout.txt) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [plan-normal.stderr.txt](plan-normal.stderr.txt) | 4586 | `9d0e14db981a742be1d624d96e9a0ce426bb2309f5f669dcab83154ce94dc6fa` |
| [worker-normal.stdout.txt](worker-normal.stdout.txt) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [worker-normal.stderr.txt](worker-normal.stderr.txt) | 808 | `4cdecf4d7ed506a81be0c93cd2a87d547c0a67dcdc35e5fe87a5b604862b3bc3` |
| [plan-optimized.stdout.txt](plan-optimized.stdout.txt) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [plan-optimized.stderr.txt](plan-optimized.stderr.txt) | 4586 | `0415d31b30104245c1cde56779f1a0d52ff1bfa52e7efd19e90af35579ea9ba3` |
| [worker-optimized.stdout.txt](worker-optimized.stdout.txt) | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| [worker-optimized.stderr.txt](worker-optimized.stderr.txt) | 808 | `1be18f1e25ea3d609e18681d6c8a246db014df30ede245b6f5023d9ab3b9e2d0` |
| [independent-composition-review.json](independent-composition-review.json) | 7450 | `0d9e51720a4ed06656149e2412857d648bf6f0418f036f339f0ae8952686390e` |

This qualification child adds only this directory's 13 files. It changes no
source, maintained tests or prior evidence. The local adapters contact no
provider or installed worker, and no GitHub Actions run or main-branch adoption
is established by these records.
