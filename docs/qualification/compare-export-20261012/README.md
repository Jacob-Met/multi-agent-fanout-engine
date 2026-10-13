# Independent receiving for comparison file exports

The existing [comparison save contribution in PR #41](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/41) lets a caller save a complete plan comparison without replacing an existing report or either input plan. This additive contribution preserves that implementation, guide and three owner-authored tests, and adds four independently received export tests plus the complete receiving records.

Run the maintained comparison tests from the repository root:

```sh
python -S -B -m unittest discover -s tests -p 'test_compare*.py' -v
```

The [four added methods](../../../tests/test_compare_export.py) check exact stdout/file bytes and input hashes, literal Unicode and punctuation filenames, both input files' bytes/inodes/mtime, occupied destinations, hard-link and symbolic-link aliases, dangling symlinks, invalid or missing second inputs, and absent output parents. The [comparison guide](../../compare-plans.md) describes the user command.

## Results and source attribution

| Received source | Result |
| --- | --- |
| Original `dca36bef09f39a2b339cc116051b5784619f71ee` plus the four new test methods as a test-only receiving addition | The 179 existing methods remained passing; the new methods produced 13 failing subtest entries because the original CLI has no `--output` option. |
| Independently authored candidate `3902656feab39b45271dbe7e8d2d5a1d3ee29665` | All 183 methods passed in normal and outer-`-O` unittest runs. A separate 31-process CLI campaign passed its expected outcomes, including 15 explicit `-O` processes. |
| Owner PR #41 at `6de0e2d4f0e83d24ad238c1634a9ede6b23ae854` | Its changed 13-method comparison test module passed normally, with no skips or failures. |
| Exact owner source plus the unchanged four added methods | All 186 methods passed normally, with no skips or failures. |

The ten production modules in the two candidate commits are byte-for-byte identical. In particular, both use comparison blob `fb478246d94d6dfab6671910a641f86eab60d78c` and the same unchanged exclusive file publisher. The later qualification establishes source equivalence and test composition; it preserves the original attribution of the earlier executions.

The independent CLI campaign also received process-local injected fsync and staging-cleanup failures, and real two-process competition at the publication boundary. A pre-publication failure leaves no partial report. A cleanup failure after publication returns failure while retaining the complete report. Competing publishers preserve one complete winning report. All source projections remained unchanged.

The native receiving environment was Linux x86_64, Python 3.14.4. The outer unittest optimization flag does not propagate to child commands; only the 15 explicit `-O` CLI invocations establish optimized CLI receiving. No new Windows or macOS execution, hosted Actions, installation or live worker behavior is claimed.

## Exact retained records

- [Source-equivalence and composition note](source-equivalence.md): the receiver's unchanged note with full source pins, commands, scope and replay limits.
- [Original receiving packet](receiving-original.json): 75 exact UTF-8 records, including all command streams, receipts, manifests and both receiving scripts. Size 316,009 bytes; SHA-256 `c5de908656667581dbcd2a331441348e7125906f1c745d3d664ebfed0013c417`.
- [PR #41 receiving addendum](receiving-pr41.json): 12 exact UTF-8 records, including the two new harnesses, focused/full-suite streams and receipts, complete tree comparison, and the previous 48-file source payload. Size 726,749 bytes; SHA-256 `7538633e5b23314c9cdd9003b95e0819f19721bdae5983bb75247a7b1b477912`.

Both packets bind each embedded file's byte count, SHA-256 and Git blob identity. Together they retain the source content needed to reconstruct the qualified projections. The harnesses preserve their original host assertions and exclusive workspace creation. They are exact execution records; a receiver adapting their paths or host assertions must record the adaptation and a new harness identity instead of overwriting prior qualification directories.

This branch is stacked on the existing PR #41 source branch. It does not modify that branch or transfer implementation or integration ownership. The original independently authored three-file candidate remains available by commit for provenance; this delivery adds its complementary test and receiving evidence to the existing owner's contribution.
