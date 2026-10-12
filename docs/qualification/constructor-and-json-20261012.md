# Constructor snapshots and finite JSON: native qualification

Date: 2026-10-12

This change prevents caller-owned lists from changing a retained Plan under its existing digest, and makes strict_json_loads reject overflowing numeric tokens. It adopts the earlier authors' exact constructor/parser edit spans and maintained tests onto the current accepted graph implementation.

## Current-source composition

The source parent is `7a05c33c63b309425b5904914e9faf589ce7aff7`, tree `c96135f157822e3de764da2ec10d6963c06330af`. That commit already contains the iterative prerequisite-count graph validator and its [native qualification](deep-dependency-graphs.md). This contribution preserves its entire _check_acyclic body, existing tests, guide and README explanation.

The final `fanout_engine/plan.py` is 6,936 UTF-8 bytes, Git blob `e64757e8e422971a49979b87705e0e4d4991fa11`, SHA-256 `363e297426c2512a19a6a059f27aea488e14d61f9ea1a3e76b54b8fb56a50189`.

Removing only the received math import, parser replacement and three tuple assignments with the added Part method wrapper restores the complete 6,446-byte parent module byte for byte. The existing graph body does not change.

| Received work | Original ownership and source | Maintained regression identity |
| --- | --- | --- |
| Constructor tuple snapshots | estate-6267db2cfc6e; [complete source](https://github.com/Jacob-Met/hamon/issues/140#issuecomment-6072503535), [receiving index](https://github.com/Jacob-Met/hamon/issues/140#issuecomment-6072555014) | test_constructor_snapshots.py, 7,836 bytes, Git `28a7c5f4ff9ccfa484019828f342b3fcc2200335` |
| Strict JSON float finiteness | estate-c36a60df2cc1; [complete reviewed proposal](https://github.com/Jacob-Met/hamon/issues/140#issuecomment-6093858194) | test_strict_json_finite_numbers.py, 7,104 bytes, Git `2d0af4a8e3fcd28a5ea76a86f1e65dd3c1f60abf` |

Both regression files and the added constructor README paragraph retain their exact donor bytes. The older reviewed chain also contained a different iterative graph walk. That full module was received and tested before main advanced, but it is not used as a replacement for the newer accepted validator. Its duplicate graph guide/tests are not part of this contribution. Source convergence is recorded in [HAMON #140](https://github.com/Jacob-Met/hamon/issues/140#issuecomment-6131859249).

## Resulting behavior

Direct Part and Plan construction snapshots the already admitted dependency, tag and part lists as tuples. Later caller mutation cannot replace a recorded instruction, change dependency readiness or change serialized tags under an earlier digest. The original Part objects, declaration/dependency order and repeated direct tags remain intact. Plan.from_dict retains its existing tag normalization. This is not a general iterator/generator contract.

strict_json_loads performs ordinary float conversion and returns finite results unchanged. It rejects an overflowing numeric token at a scalar or nested position with the existing `PlanError("non-finite JSON number")` diagnostic. Finite values, signed zero, finite underflow, integers, object order and numeric-looking strings remain unchanged, as do named-constant and duplicate-key refusals. It adds no new integer, Unicode, document-size or nesting policy.

Ledger transitions, route selection, dispatch, inspection, the preview consumer's 256-part limit and the separately owned interrupted-transaction work are outside the source change.

## Native qualification

CPython 3.12.14 on Linux x86_64 ran the actual package and standard library. All ledgers and adapters were local fixtures. Source and test hashes remained unchanged throughout execution.

| Exact source | Actual result in normal and genuine -O execution |
| --- | --- |
| Current parent 7a05c33, with the same 66-method expanded suite | 11 failed checks in each mode: five constructor methods and six overflow subtests; no errors |
| Composed candidate, with all 50 existing and 16 added methods | 66/66 pass in each mode, zero skips |
| Existing demo.py and inspect_plan.py | Both exit 0 |

The negative controls expose the remaining current-main defects: externally changed lists alter stored identity/readiness or dispatch payloads, and six overflowing numeric documents return values instead of the promised error. These are 11 failed checks, not 11 failing methods. The existing graph tests pass on the current parent and on the composition.

Reproduce the maintained qualification from the repository root:

```sh
python -B -m unittest discover -s tests -v
python -O -B -m unittest discover -s tests -v
python -B examples/demo.py
python -B examples/inspect_plan.py
```

The preserved strict-number test header describes its original source-only authorship stage. This dated record supplies the later execution status; its historical text has not been rewritten into a new result.

## Publication and limits

The complete sole workflow, `.github/workflows/test.yml` at blob `8fc1b6dab1d4b4f3ce5dff9748ba6b1e0c137b53`, has only push and pull_request subscriptions. Source publication uses `[skip ci] [skip actions]` in source and merge commit messages under the standing no-Actions direction. No workflow file is changed or dispatched.

These observations qualify the source on the recorded native runtime. They do not establish a hosted Python 3.10/3.11/3.12 matrix, a live provider or worker result, installed estate adoption, production capacity, or unlimited graph size.
