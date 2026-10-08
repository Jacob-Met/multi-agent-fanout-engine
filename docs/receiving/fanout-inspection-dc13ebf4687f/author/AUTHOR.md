# Retained-project inspection qualification

This source contribution adds `inspect_project(ledger, project_id)` to the existing public reference package. An operator can inspect the stored plan, native task/artifact/evidence references, each direct unmet prerequisite, and the observed queued/dependency-ready intersection without supplying another Plan or invoking an adapter.

## Source and ownership

Repository: `Jacob-Met/multi-agent-fanout-engine`, baseline main `d65bde9c59b1d2593a80f6d838c0a40bf6768013`, complete tree `d5e5ad4e316be0b20a50151f8549ac490d3d99de` (12 files). The six changed product paths and all preserved inputs are bound in `source-manifest.json`; `candidate.patch` is the exact baseline-to-final patch. The final candidate is v2. No local source commit or deployed estate adoption is claimed.

[The central scope claim](https://github.com/Jacob-Met/hamon/issues/140#issuecomment-6062467135) records ownership and the lead's actual HTTP 410 project-issue creation failure. No project issue was created. The repository has Issues disabled; its empty issue response is not exhaustive ownership evidence. Our current open-PR read and central claims supplied coordination. The original discovery receipt remains historical and is qualified by this later observation. No repository settings were changed.

## Decisive comparison

The original eight-part authored ledger has five dependency-ready parts and four queued parts, but only `notes` belongs to both sets. Existing low-level methods behave as documented. The new report gives that intersection plus every part's retained native state and direct blockers in one coherent read. `verify` is blocked by unknown `fetch`; `signoff` by failed `benchmark`; and `publish` by three unfinished direct prerequisites. The API neither predicts task fitness nor reserves dispatch.

The native constructor compatibility witness is substantive: direct tags `zeta, alpha, zeta` have a different native digest from the normalized `Plan.from_dict` tags. Inspection validates the stored plan while preserving its original tag order and duplicates. All 21 old Ledger methods and the entire predecessor ledger text are recovered by removing the single added snapshot method; the old README and exports are preserved. Schema, dispatch, routing, transitions, retries and reconciliation are unchanged.

## Qualification and source versions

| Boundary | Actual result |
|---|---|
| Historical v1 memory source, normal / optimized Python | 17 methods passed in each mode |
| Historical v1 normal filesystem discovery | 17 methods passed |
| New integer-limit regression on v1 | One method, two expected raw-ValueError subcase errors |
| Final v2 memory source, normal / optimized Python | 18 methods passed in each mode, zero skips |
| Final v2 normal filesystem discovery | 18 methods passed |
| Final example invoked by absolute path from /tmp | Eight parts; only notes ready |
| Final retained disk ledger, two fresh child processes | 17 receiving checks passed; bytes/inode/mtime and eight event rows unchanged |

All local runs used CPython 3.12.14. The unchanged repository CI targets Python 3.10, 3.11 and 3.12; those remote checks are not claimed here. The configured integer-limit case explicitly skips only on an interpreter without an active limit; it did not skip in either recorded local mode.

Every test inspection runs with SQL writes/transactions denied, exactly one traced SELECT required, and the complete native database dump compared before/after. The exact memory harness additionally blocks filesystem writes, non-memory SQLite, subprocess creation and socket connects; it recorded zero blocked attempts. Its fixed test adapters are authored fixtures, not actual Hub/provider sessions.

V1 exposed a narrow refusal-contract gap: Python's configured JSON integer-conversion limit raised raw ValueError. V2 changes only that decode boundary and adds the actual stored-route/evidence regression. It neither changes parser limits nor catches arbitrary evaluator failures. The earlier raw probe confirms unchanged ledger rows. `v1-to-v2.json` binds the two changed files; all other v1 bytes remain exact.

## Receiving and replay limits

`memory_qualification.py.source` is the exact executed, self-contained memory-source harness. Invoke it explicitly with Python (and optionally -O); its .source suffix prevents automatic test collection. The candidate's normal supported entry is `python -m unittest discover -s tests -v`; the new example is `python examples/inspect_plan.py` from a source checkout. No dependency installation was used.

`disk_reopen.py.source` preserves the exact historical disk receiving driver, including its original exclusive fixture path. It is not an idempotent portable command: a reviewer must choose a new authored fixture directory and the exact received candidate path before a separate run. It refuses an existing fixture. The authored SQLite database stays outside the publication allowlist; the recipe, complete result and database hash/stat identity are retained. The first optional attempt stopped at a zero-free-byte gate before any fixture creation; later positive capacity allowed the recorded v2 run. No frozen material was removed to obtain space.

The consumer accepts an already-open native Ledger. Reopening the authored disk fixture used the unchanged Ledger constructor, which initializes missing schema; this is not a new read-only database opener or repair tool. The disk witness does not qualify WAL writer contention, a live adapter, serving activation or estate capacity. It shows one locally retained authored project can be reopened and described without modifying its bytes or interpreting unknown outcomes as completed/queued.

Only literal authored data was used. Reference locators were preserved as data and never opened. The actual gain is the complete stored-project inspection workflow; no latency, throughput, deployment or paid-provider gain is claimed. Independent receiving and the ordinary PR/CI gate remain the lead's next step.
