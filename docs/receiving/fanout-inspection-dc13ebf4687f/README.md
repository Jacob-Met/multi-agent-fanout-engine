# Retained-project inspection: source and receiving evidence

This increment gives callers an existing-ledger review step:

```python
from fanout_engine import inspect_project

report = inspect_project(ledger, "existing-project")
print(report["queued_ready_ids"])
for part in report["parts"]:
    print(part["id"], part["state"], part["unmet_dependencies"])
```

The caller needs an open Ledger and a stored project ID. The API reconstructs
the retained native plan, reports every native state and reference, and shows
direct unfinished prerequisites. It reads one SQL snapshot and changes no state.
It does not need an external Plan copy, Hub or route catalog. Ready IDs are an
observation, not a reservation or evidence of remote completion.

## Qualification

The six product paths are pinned in
[author/source-manifest.json](author/source-manifest.json). The original
21 Ledger methods, plan/routing/dispatch source and other nine unaffected
baseline files are preserved.

[Author evidence](author/AUTHOR.md) retains the original missing-capability
comparison, native tag identity control, v1 integer-limit failure, repaired v2
results, default discovery/example and disk-reopen observation. Its exact
27-file carrier includes the original discovery receipt through an explicit
source override; the interrupted duplicate is excluded.

[Independent acceptance](independent/REVIEW.md) binds a native oracle frozen
before candidate/author-test reads. Fifteen guarded reads matched the native
values and typed errors, preserved caller transactions and detached values,
and retained a coherent snapshot while another connection committed changes.
The actual run passed 123 assertions; no inherited suite was repeated.

[Receiving preflight](receiving-preflight.json) observes the original main
`d65bde9c59b1d2593a80f6d838c0a40bf6768013`, its exact 12-file tree,
and zero open pull requests. The publication map keeps the three old-path
preimages and the three new-path absence requirements. The nine unrelated
baseline files must remain unchanged.

## Custody

This directory is evidence outside test discovery. Historical harnesses retain
their original absolute-path assumptions; they are not added product commands.
Synthetic databases, caches, the old physical v1 candidate and interrupted
outputs are excluded. Author source and negative evidence are unchanged.

All 45 publication paths are listed in PUBLICATION-ALLOWLIST.txt.
COPYMANIFEST.json binds the other 44; the external publication map binds all 45.
Physical files are referenced directly. Small explicitly virtual carriers avoid
copying checkouts or retrying ENOSPC writes; the empty independent REVIEW.md
from a failed write is superseded by its complete supplied bytes.

Qualification is authored local reference behavior. No installed estate,
external adapter, provider, account, live ledger or dispatch was exercised.
The initial hosted Python 3.10 job exposed a test-cleanup incompatibility after the guarded inspection completed: `set_authorizer(None)` only disables the callback on Python 3.11+. The product implementation was unchanged. The accepted successor installs a callable returning `SQLITE_OK` only in the helper's `finally` block; the strict guard remains active throughout inspection. The raw failing job, author receipt and independent review carrier are retained under `hosted/`.

Main advanced independently to `82b5a03a2d3ebaaad13841b3b9b3ffbc55ddff1d` with the authored-plan preview. The independent composition carrier binds that 51-leaf tree, the exact additive README composition `588f3cdecdb444260844d3dcf30fabe22527e150`, the corrected test `57fb1e80af400f4b7cfdb0fbac5bae34001f1b9a`, 64 composition checks, and the unchanged product blobs. Hosted CI on the updated PR head remains the final source-integration gate.
