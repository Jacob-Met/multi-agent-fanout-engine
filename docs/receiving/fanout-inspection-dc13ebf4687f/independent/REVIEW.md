# Independent fanout inspection acceptance

Accepted the exact six fanout v2 paths against original main
`d65bde9c59b1d2593a80f6d838c0a40bf6768013`. The key runtime blobs are
inspection `2944a58dae77ce7b5bf91f0637d4c5e7686c7e34` and ledger
`28e8eeafa37a9faceebddff7de1894cc35fe189b`. The full 15-file map is in
[review-receipt.json](review-receipt.json). No correction is requested.

## Independent result

Before reading the inspector or any author test body, the reviewer froze a
nine-part oracle using only the original native Plan and Ledger API. It contains
all six native states, non-topological part order, repeated ordered tags,
nested route/evidence values, literal Unicode, and distinct direct blockers.
The original dispatcher predicate yields exactly `["ready", "queued"]`.
The new report matched every expected field. It preserved the original digest;
normalizing the repeated tags through Plan.from_dict would change that digest.

One normal-mode run passed **123 assertions across 15 guarded inspection calls**:
eight reports and seven expected typed refusals. These are assertion/call counts,
not 123 separate scenarios. Every call used one compound SELECT, requested no
write, transaction, pragma or SQL function, and preserved the connection's
transaction state and change count.

The complementary boundaries were:

- Deep edits to returned tags, dependencies, blockers, counts, route/evidence and
  raw snapshot dictionaries did not alter a later report, native events or the
  original database bytes.
- An existing caller transaction saw its own prior uncommitted change. Inspection
  left it open; explicit caller rollback restored all rows.
- Missing expected rows, wrong keys, a payload whose normalized tags conflict
  with the retained plan, a decoded surrogate route, extra parts, a wrong plan
  digest, and an absent literal project returned the documented error codes
  without a partial report or transaction effect. A closed SQLite connection's
  ProgrammingError propagated unchanged.
- A deterministic WAL barrier held the reader after fetching its project header
  while another connection performed two native completion transitions. Both
  committed before the reader resumed. The first report remained completely old;
  the next saw both commits and the newly eligible dependent.
- A caller-owned read transaction retained its snapshot across another
  connection's native dispatch until the caller ended that transaction.

The WAL observation is consistent with
[SQLite's documented isolation](https://sqlite.org/isolation.html). Actual
qualification is CPython 3.12.14 / SQLite 3.53.1 on the local Linux runtime,
using two connections in two threads. No multi-process/distributed guarantee,
shared-cache read-uncommitted behavior or concurrent write through the same
connection is inferred. Readiness is an observation, never a dispatch reservation.

## Custody and limits

All 15 candidate files and all 12 original inputs matched their pins. Removing
the single added ledger method recovered every predecessor byte; all 21 original
methods remain exact. Public imports/exports are additive; the original README
is retained. Author tests were read statically only after independent execution.

The oracle is [native-oracle.json](native-oracle.json), SHA-256
`01510b42676795d65a3072ad3e9876c7fcc10f2b170ecf67b645cfd277008da7`.
The [review receipt](review-receipt.json) is SHA-256
`d27fcc9b0e8ccad35b0bfa6a4e52f1744daa616cfa9c412f68e05f5df4547053`;
[run-observation.json](run-observation.json) records the actual exit-zero call.

The two Python files are historical programs with exact absolute paths and
exclusive authored-output expectations, not new portable product commands.
Their SQLite fixtures are excluded from publication. No author/inherited suite,
optimized replay, integer-limit regression, live ledger, adapter, Hub, router,
provider, account or remote action was run. References remained data.

A packaging ENOSPC left an empty local REVIEW.md. That empty file is preserved
and excluded; this complete supplied text supersedes it. The source, oracle,
program and successful receiving receipt were already frozen and remain exact.
