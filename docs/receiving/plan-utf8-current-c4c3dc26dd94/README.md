# Saved-plan callers receive the public PlanError

This current-source receiving course covers the existing PR37 constructor fix. A caller that catches `PlanError` can refuse an instruction containing an unpaired surrogate without an uncaught encoding traceback. Ordinary multilingual content must retain its exact serialized document, digest and idempotency key.

The bounded original-first course improved from 1/2 desired behaviors to 2/2. The candidate preserves the complete ordinary output and lets the caller handle malformed text through its existing domain-error branch.

## Source and ownership

The offer is [PR37 at 8ef458d](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/37). Its complete `fanout_engine/plan.py` is Git blob `c1de111f502848221639246ba0bc35781d7c953d`; the unchanged three-method test is `9679168c6108f78e4a1b09e511f50e8df114423d`.

The receiving baseline was commit `e3ef5fe2da8f6520ee134b8bf5e792a4c00e51e3`. Its full plan file equals the offer's parent. Removing only the added `try/except UnicodeEncodeError` recovers that whole current file. The other five current package modules remain exact, including the newer ledger module. Importing the package does not construct a ledger in this course. After PR107 merged as `0ae18b605965be749b1651545ba7531a5fb03e00`, all six receiving module blobs still matched the frozen baseline.

The separate PR54 mutable-snapshot and idempotency-key work, the PR92 leading-line-feed continuation, and installed reader wrappers remain outside this change. The original PR37 offer and its historical receiving are retained.

## Actual consumer contract

An authored offline caller imports the actual public `Plan` and `PlanError` classes, loads one owned JSON fixture, and invokes `Plan.from_dict`. It catches only `PlanError`, emits a contextual diagnostic and returns 2. On success it calls `to_dict` and `idempotency_key`, then emits the full document, digest and key as canonical UTF-8 JSON plus a final line feed.

The ordinary fixture contains Arabic, Hebrew, café, snow-character and emoji-with-ZWJ text. Its expected 315 output bytes were frozen before candidate source inspection. The malformed fixture contains one escaped high surrogate. The desired refusal is no stdout, exit 2, a UTF-8 diagnostic and no traceback.

| Fixture | Original observation | Candidate observation |
|---|---|---|
| Ordinary multilingual content | Exit 0, exact 315 bytes, empty stderr | Exit 0, the same 315 bytes, empty stderr |
| Malformed instruction | Exit 1, empty stdout, 796-byte UnicodeEncodeError traceback | Exit 2, empty stdout, clean 62-byte PlanError diagnostic |

The original desired result is 1/2. Its receiver's exit 0 means the expected original failure was captured correctly; it does not turn that product failure into a successful refusal.

## Receiving scope

The actual venue is cloud Linux with CPython 3.12.14. Each phase has two real child processes, a four-second direct-child bound, raw stdout/stderr capture and kill/communicate/reap on timeout. The original 12 input identities are unchanged; all 17 original inputs and outputs are frozen for the candidate phase. The candidate phase preserved all 25 selected input identities, including those original artifacts, while checking the same two behavioral expectations. All four product children were reaped without timeout. Each enclosing receiver/helper completed with exit 0 and unchanged selected source maps; the original outer completion and the candidate initial terminal response are retained.

The caller uses in-process audit fences against connections, process creation, SQLite connections and file mutations. This is a bounded trusted-fixture course, not an OS sandbox. There is no native installation, browser, Hub, provider, real ledger or dispatch operation.

The existing owner's three-method tests and earlier macOS/Windows reports are historical qualification, not repeated here. The current receipt is a small public-API consumer check. It does not repeat their full suites or optimized-Python runs, broaden Unicode policy, or claim protection against hostile object behavior.

## Evidence and use

The source/oracle peer independently read the complete owner/current delta, caller and frozen expectations before candidate execution. Current raw-result receiving is recorded separately from historical owner reports. The original and candidate receipts are retained verbatim; their product statuses are 0/1 and 0/2 respectively.

Two preparatory corrections are preserved as unexecuted history: the independently written expected key acquired the actual public `fanout-` prefix before the original run, and a post-PR107 metadata draft was corrected to take the tree SHA from the immutable commit rather than the tree lookup response locator. Neither caused a product replay.

The accompanying receiving packet contains the exact current package projection, unchanged owner test, two fixtures, caller, receiver, full raw streams, process/helper records and original/candidate receipts. Integrity verification is separate from executing the product. Retained drivers refer to their original absolute work directory; they are evidence rather than a portable rerun command.

A normal application can handle invalid saved plan input through the established public exception:

```python
from fanout_engine.plan import Plan, PlanError

try:
    plan = Plan.from_dict(saved_document)
except PlanError as error:
    report_invalid_saved_plan(str(error))
```

The caller supplies its own reporting function and ordinary JSON admission policy. This change only restores the existing constructor exception boundary.


The exact clean diagnostic is:

```text
saved-plan caller: plan contains text that is not valid UTF-8
```
