# Project catalog on the current ledger

This record qualifies the project catalog after composing it with newer ledger
read behavior and preserving the subsequently integrated comparison exporter.
The original catalog source, guide and qualification remain unchanged.

## Exact source

| Role | Commit | Tree |
| --- | --- | --- |
| Current main for complete-suite and transaction receiving | `27502202fe2429eef11740d23a8e760c4a7d9fc5` | `cfaca3669bb7546d997b29e1a61404c7602bdc5d` |
| Catalog composition for that receiving | `bfd43a8f33f1f4b1376b4b8211458daef7ed5f3f` | `bd1b9a1ee6ca44278ec014deb3770565fa02ca67` |
| Later current main with comparison exporter and guide correction | `cb30577caedeb2d722abf74047b42407d0c7f995` | `e27bf988796671467430854edb58ecbc13f7aea1` |
| Comparison-export union | `eda3b524ad9a1997e6973a7ee3ed1ca109bce027` | `e5f165d8691cb0b864f02104befe4397d939f538` |
| Current main after initializer cleanup | `484ad9270b6c5e49db87171eb26ac516d592ddd6` | `3eb9d157062e3998fad452e08b6e0613bc152635` |
| Final source union | `3b2706a32e2e395bb7282b83ea18d3ac2cd576d9` | `4491a6b4adba678d1cd4cab230337446d746bbf2` |

The final source has ordered parents `eda3b524...` and `484ad927...`. Its 213
leaves preserve all 206 unrelated current-main leaves, modes and types. Five
original catalog files are added, while README and ledger receive their exact
reviewed insertions. Removing the 578-byte catalog method restores the entire
current ledger. All 25 preexisting method ASTs remain unchanged. Removing the
564-byte README section restores the entire current README.

The only runtime-module change between `bfd43a8...` and `eda3b524...` is the
independently integrated `compare.py`. The catalog and its imported dependency
closure remain exact in that comparison union. The subsequent final union also
preserves main's newly accepted initializer cleanup. Only `Ledger.__init__`
changes relative to the prior composition; every other method and the exact
catalog insertion remain unchanged. No adjacent plan-persistence or dispatch
draft is adopted.

## Qualification

| Course | Exact source | Result |
| --- | --- | --- |
| Complete maintained Linux suite | Current `27502202...` | 193 passed, no skips |
| Complete maintained Linux suite | Catalog `bfd43a8...` | 204 passed, no skips |
| Catalog with actual Python `-O` | Catalog `bfd43a8...` | 11 passed, no skips |
| Independent real-SQLite transaction receiving | Current `27502202...` / catalog `bfd43a8...` | Four direct-inspection controls / four catalog handoffs accepted |
| Affected comparison API and actual CLI tests | Comparison union `eda3b524...` | 17 passed, no skips |
| Affected initializer and catalog tests | Final union `3b2706a3...` | 2 initializer + 11 catalog passed, no skips |
| Independent source and guide review | `bfd43a8...`, `eda3b524...` and final union | ACCEPT for their exact source scope |

The author courses used Linux CPython 3.12.14. The independent transaction
receiver used Linux CPython 3.12.14 and SQLite 3.53.1. It authored separate
controls for pending writes, inspection refusal, an explicit WAL snapshot, and
catalog CLI discovery followed by exact-ID inspection. A real second connection
confirmed that reads preserved the caller's pending marker and rollback. A WAL
reader retained its old catalog and queued state across the writer's committed
new project and dispatch, then observed both changes only after explicit
rollback. The final closed-file CLI handoff preserved the database bytes, inode,
mode and modification time.

Current main has no catalog command, so its four direct-inspection controls and
the candidate's four catalog handoffs are not identical paired catalog tests.
Fixture setup intentionally writes disposable SQLite state. Database
conservation applies to the final closed-file CLI handoff, not fixture setup.

The complete suites use exact 62-file current and 67-file candidate projections
containing all maintained tests, runtime modules, examples and test fixtures.
They omit unrelated repository receiving documentation. All 129 source files
retain bytes, modes, inodes and timestamps. The comparison union uses a 68-file
projection for the 17 changed comparison tests, with the same source checks.
The latest initializer union uses a 69-file projection for its 13 affected tests.
The earlier independent transaction receiving remains bound to `bfd43a8...`;
the constructor cleanup is qualified by the separate final-union course.
Actual import paths, hashes, optimization levels and terminal results are
recorded. The complete suite was not rerun or relabelled as a final-union course.

The Mac became explicitly offline before current-composition tests started.
The initial source-transfer write failed with a device timeout; partial file
effects remain unknown pending readback and the write was not repeated. A
separate optional custody-directory creation also timed out; no archive chunks
were transferred. These are access failures, not product failures. No new Mac
qualification is claimed. Earlier Mac results remain bound to the original
catalog source.

## Evidence and limits

[`receiving.json`](receiving.json) names the exact source pins, raw receipt
lengths and SHA-256 hashes, replay scripts and scope limits. Raw original
receipts, including integer nanosecond timestamps, are preserved unchanged in
the separate current-composition evidence companion. Later publication and main
integration remain distinct events.

The original [catalog replay kit version 3](https://drive.google.com/file/d/1dyRf1h8138QEQe5zYKQ5LyTJSXxg8399/view)
remains unchanged: 827,349 bytes, SHA-256
`03ecc2f0a50c332b37ae752cd813d0b9247edf5132d155c5b50a5344b2b28cbc`.

The catalog reports authored-plan identities and counts. Existing inspectors
retain detailed runtime-part and event validation. SQLite WAL transaction
visibility is not an immutable filesystem snapshot. Receiving uses authored
local data and makes no installed fleet, provider or service-adoption claim.

Workflow source is unchanged and no Actions workflow was dispatched. Local
courses provide the test evidence; an empty pending hosted-status set is not a
hosted test pass. Publication and merge run counts are checked separately.
