# Project catalog qualification

The new projects command lists retained native plan identities so an operator
can discover an exact project ID before using the existing project or history
inspector. Usage and all behavior limits are in
[the project-catalog guide](../../project-catalog.md).

## Source reviewed

- Repository: Jacob-Met/multi-agent-fanout-engine.
- Base commit: `dca36bef09f39a2b339cc116051b5784619f71ee`.
- Base tree: `8e28ee92cd7e03fbaa211dbff69ecfe65d4924ce`.
- Reviewed source candidate: `999d1a3a528669ca6a4b0a62aeb8dd5ab9b1c61c`.
- Reviewed candidate tree: `ade813bb4affc767942aefc89769574830cd92fd`.

The four source/guide paths are `fanout_engine/ledger.py`,
`fanout_engine/projects.py`, `tests/test_projects.py` and
`docs/project-catalog.md`. Removing the 578-byte additive snapshot method
restores the entire original ledger exactly. The candidate adds three files,
modifies only that ledger file, deletes nothing and preserves all 170 unrelated
baseline leaves and modes. The evidence files in this directory are an additive
qualification record; the reviewed source bytes are unchanged.

## Executed results

| Receiving course | Original | Candidate |
| --- | --- | --- |
| Linux CPython 3.12.14 complete maintained suite | 179 tests, no failures or skips | 190 tests, no failures or skips |
| Linux focused ordinary-file tests | Capability absent in original | 11/11 normal and genuine -O |
| macOS CPython 3.13.7 complete maintained suite | 179 tests, four existing skips | 190 tests, same four skips |
| macOS focused ordinary-file tests | Capability absent in original | 11/11 normal and genuine -O |

The four macOS skips concern the absence of `/dev/full`; they are unchanged.
All local processes use ordinary native CPython and SQLite. Initial Linux
filesystem exhaustion required a small in-memory source-loader witness and six
native SQLite API tests; those early results are kept separately from the later
ordinary-file runs. The Linux source/test/example/guide projection contains
57 original files, each verified against its Git blob. macOS receiving used the
frozen Git checkout and separately verified the candidate tree and hashes.

The focused course covers deterministic identity order, complete plan
validation, detached values, one SQL snapshot, caller transaction preservation,
runtime-row scope, empty and incompatible input, actual module CLI use,
exclusive-new-file output, selected-database preservation and committed WAL
visibility.

A separate macOS receiver authored another ledger under a path containing spaces
and Unicode. Discovery returned `alpha-receiving` and `zulu-receiving`. Passing
the first exact ID into the existing inspector returned the expected digest,
two authored parts, ready `read` and blocked `review`. The database SHA-256 stayed
`98bffa01f1fb3ecf0f06197990a4bb179df1acbfc69a342a59739a599f88bfa4` across both
read-only commands; stderr was empty and tracked source stayed clean.

## Independent disposition

The separate shared-delivery reviewer accepted the exact frozen candidate for
isolated review-branch publication after reading all source, tests and guide
changes plus their existing validation, opening and output dependencies.
It verified full-tree conservation and the exact ledger inverse. Its static
acceptance is distinct from the runtime worker's native execution evidence.

[receiving.json](receiving.json) records source hashes, the original witness,
author results, native receiver results, the independent handoff and source
disposition.

These results qualify a source increment and authored local consumers. They do
not establish installed fleet adoption or provider behavior. The catalog reports
authored-plan counts; detailed runtime and event validation remains with the
existing inspectors. No default-branch update, release or hosted workflow result
is claimed here.
