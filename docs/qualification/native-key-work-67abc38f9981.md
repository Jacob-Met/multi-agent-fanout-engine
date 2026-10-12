# Keep native Plan key lookup work bounded

This contribution adds two maintained tests to the Plan membership implementation
accepted through [PR17](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/17).
It changes no production code. The accepted owner's conditional cache and its
live mutable-input fallback remain the implementation.

## What the tests protect

The existing six key-identity tests all pass on the original uncached Plan.
`test_complete_native_key_passes_have_linear_part_read_work` adds a deterministic
work bound for the improvement itself. It makes three complete key passes plus
an unknown lookup at 39 and 151 parts and independently calculates every key.
The observer counts reads of native `Part.id`, returns every attribute unchanged,
and keeps the exact native Part and str types. A string subclass would take the
accepted implementation's intentionally uncached compatibility route and would
not measure this optimized path correctly.

The test permits four full linear passes. It does not assert elapsed time,
private cache names, one exact implementation or one machine's speed.

`test_native_and_mutable_parts_keep_live_mixed_membership` retains the established
behavior of an admitted mutable Part-like object alongside a native Part. Both
authored orders are exercised. After the lookup is warm and the mutable ID is
changed, the old ID must refuse, the new ID must use the established key formula,
and the native part's key and both original object identities must remain intact.

## Differential evidence

| Source | Native ID reads at 39 / 151 parts | Native work bound | Mixed membership, both orders |
| --- | ---: | --- | --- |
| Original Plan | 4,602 / 68,554 | Refused | Preserved |
| Withdrawn unconditional-cache prototype | 39 / 151 | Passed | Refused |
| Accepted PR17 Plan | 78 / 302 | Passed | Preserved |

The same outcomes were received in ordinary and genuinely optimized Python
3.12.14. The accepted Plan passes both new methods; with the owner's six existing
identity methods, all eight focused tests pass in both modes. An independent
worker reviewed the complete test and reran all six original/prototype/owner
phases, reproducing the expected two failing subcases in each negative variant.
The accompanying JSON files preserve exact source hashes, commands and raw
diagnostics. No current whole-repository or Windows test result is inferred from
this focused receiving.

The unconditional prototype was developed locally during parallel estate work,
then withdrawn before any source publication when PR17 and its stronger
compatibility handling were discovered. Its earlier native-only passing results
do not qualify the missed mutable-input boundary. That negative is retained here
to show why both maintained tests matter; the prototype is not included as
production source.

## Source and replay

Publication parent: `77217a07a76e8ee6554ffe11808b1bdcbaf680ee`, complete root tree
`a2e9d90f2491dd42706309f798b84d00603c0ec4`.
The accepted Plan is Git blob `69a633cacd6f32e8bbc6d0d580db3b2fcb14ec82`, SHA-256
`884f85eff1ef526a8a47e6ee258fc473ce6647e914bd93298d91824640deab61`.
It is byte-identical to the reviewed PR17 source used by these controls.

Test SHA-256:
`86600c4d8631e0fc98e9d2d0ac332efcd2a1a179ac0ddb468be7cda945196b5c`.

From the repository checkout:

```sh
python -m unittest discover -s tests -p 'test_native_plan_key_work.py' -v
python -O -m unittest discover -s tests -p 'test_native_plan_key_work.py' -v
```

The new path is found by the repository's existing ordinary unittest discovery.
Only this test and its qualification records are added. Every inherited source,
test, document, tree mode and workflow is preserved. The unchanged sole workflow
listens only to push/pull_request; publication carries `[skip ci] [skip actions]`
under the standing no-Actions direction. This receiving performs no remote
worker/provider operation or installed-runtime change.
