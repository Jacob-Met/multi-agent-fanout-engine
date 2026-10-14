# Exact-source receiving for fanout PR #41

## Result

The ten production modules in PR #41 at `6de0e2d4f0e83d24ad238c1634a9ede6b23ae854` are byte-for-byte identical to the production modules independently received at `3902656feab39b45271dbe7e8d2d5a1d3ee29665`. The complete Git leaf comparison includes modes, types and absent paths. The two trees preserve 169 common leaves and differ only in the comparison guide, the owner's changed comparison test file, and the earlier candidate's separate four-method regression file.

This addendum preserves PR #41's implementation ownership. It contains no production source change and does not relabel earlier native executions as executions of the newer commit.

## Native results

All runs below used the verified ThinkPad `cadafaf3-4d0b-4c4f-a0d3-34a95d2cec90`, hostname `hamon-thinkpad`, uid/gid 1000, Linux x86_64 and Python 3.14.4. All source projections are private directories under `/var/tmp`; the installed application and services were not changed.

| Source and test composition | Newly executed result | Attribution |
| --- | --- | --- |
| Exact PR #41 projection, changed `test_compare_plans.py` module | 13 tests passed; no skips or failures; exit 0 | New normal receiving run, PID 2376811; test subprocess 1.4156 seconds; outer process exit 0 |
| Exact PR #41 projection plus the unchanged four-method `test_compare_export.py` from candidate 3902656 | 186 tests passed; no skips or failures; exit 0 | New normal full-suite composition run, PID 2380491; test subprocess 15.4190 seconds; outer process exit 0 |

The two projections remain separate and preserve all source bytes after execution. The additive test file is Git blob `94f6258ada572ef8909370379a9e48e363e63234`; the owner's comparison test is Git blob `092b9fc6b4fd8553bb1a0b94e4cf75c16609e932`.

The existing receiving packet remains unchanged. It records the candidate's 183-method normal and outer-optimized suites, plus 31 separately launched CLI processes, including 15 with explicit `-O`. The original source with the four added tests produced 13 failing subtest entries in the new methods; both candidate suites passed. Existing methods did not regress. The 31-process campaign covered exact stdout/new-file bytes, input identity, occupied and aliased paths, hard links and dangling symlinks, invalid input and missing parents, fsync and cleanup faults, and two-process publication competition. Those executions remain attributed to their original source commits.

## Source identities

- Owner PR: https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/41
- Owner source commit: `6de0e2d4f0e83d24ad238c1634a9ede6b23ae854`
- Owner tree: `4483857791f6c619aaa294e53ab6934e7818987f`
- Previous received candidate: `3902656feab39b45271dbe7e8d2d5a1d3ee29665`
- Previous received tree: `15df82750364827904eed1d45244f804ad5b969d`
- Common parent: `dca36bef09f39a2b339cc116051b5784619f71ee`
- Identical comparison implementation: `fb478246d94d6dfab6671910a641f86eab60d78c`

The prior 75-record publication packet has SHA-256 `c5de908656667581dbcd2a331441348e7125906f1c745d3d664ebfed0013c417` and Git blob `b6962251dfb020c412b328e11276425b2fd1475f`. Its sealed manifest has SHA-256 `4b3379983e335ebb72e2349e17e6a942f986702d2bf5fbf5b84f7817bad9bdd7`.

## Retained evidence and replay boundary

The addendum contains exact UTF-8 records, byte counts, SHA-256 and Git blob hashes for the two new harnesses, both receipts, all four command streams, the complete tree/source-equivalence input and this note. It also includes the previous complete source input as `previous-source-input.json`, resolving the prior packet's dependency on an otherwise external `input.json`. Together these records contain the source content required to reconstruct both source/test compositions.

The harnesses retain their original host and workspace assertions and exclusive directory creation. They are an exact execution record, not a portable installer. A future receiver should reconstruct verified sources in a fresh authorized private directory and record any harness-path adaptation with a new harness hash. Existing qualification directories must not be overwritten.

The new full suite was run normally. The owner's test helper launches child Python with `-B`; it does not inherit `-S` or `-O` from an outer interpreter. User site packages were disabled through the recorded environment for both parent and child processes. The earlier explicit optimized CLI campaign is the optimized CLI evidence.

This qualification establishes isolated Linux source behavior and additive test compatibility. It does not establish new macOS or Windows coverage, installation, a running consumer, provider/Hub activity, or hosted Actions results. Parent integration ownership is unchanged.
