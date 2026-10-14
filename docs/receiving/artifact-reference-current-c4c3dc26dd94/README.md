# Completed artifact references: current API receiving

Both completed transitions now require a nonblank UTF-8 text reference before changing retained state. Valid references retain their exact spelling, including surrounding spaces, Japanese text and combining characters. This integrates the existing PR40 admission and PR61 literal-text binding into the current ledger; it does not invent a new completion policy.

The concrete consumer is a caller recording completion before inspecting what dependent work is ready. On the received original, a whitespace-only reference is recorded as completed and the dependent becomes ready. On the candidate, the same call raises `LedgerError`, the original running or unknown state remains, and the dependent stays blocked.

## Use the API

For work whose result has actually been verified, choose the transition that matches its recorded state:

```python
# Existing running work:
ledger.mark_completed(project_id, part_id, artifact_ref, evidence)

# Existing outcome_unknown work, after resolving the uncertainty:
ledger.reconcile_unknown(
    project_id, part_id,
    verdict="completed", evidence=evidence, artifact_ref=artifact_ref,
)
```

Catch `LedgerError` for a refused transition. Completion requires text that is nonblank and encodable as UTF-8; accepted text is not trimmed or normalized. The helper returns built-in string contents before database binding. A failed reconciliation keeps its existing separate behavior.

This gate does not open the reference, verify artifact bytes or authenticate an external result. The caller remains responsible for that evidence. `inspect_project` and `inspect_blockers` report recorded state and dependency readiness; a ready part is not a dispatch reservation or proof of worker capacity.

## Exact source and owner lineage

The receiving baseline is current main `10765dee0f518b28ff9ca06c4f04c5d1a6955b0f`, with ledger blob `fe545eb59a797ad4a9a05fae0f7c415c3a7f3e51`. The composed ledger is `3639750485f613337c50cc162f7339bc8da1cb0d`, 19,913 bytes, SHA-256 `c6f02773f0b4a19d3c6cc73baa5b47f36296c9bbf19ed9524453194cb598df44`.

The complete helper and both completed-transition functions are byte-exact to [PR61](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/61) head `8818b00bd38558bb677c7d9c38cff78f99a3a2f4`, stacked on [PR40](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/40) head `6856206075a825e09b980c0140547993bcc4557a`. Reversing only those three source spans recovers the entire current ledger. The current two completion functions matched the original owner parent before composition. Eight other current modules remain unchanged. The net product addition is 573 bytes.

The original three-method admission test and two-method binding test are preserved exactly. Their earlier native, optimized-Python and broader qualification remains attributed to [PR40's independent receiving](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/40#issuecomment-6134348437) and [PR61's independent receiving](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/61#issuecomment-6138104380). Those suites and specialized binding cases were not repeated here. Original owner refs and ancestry are retained. PR54 mutable-plan/idempotency work, separately owned evidence admission, leading-LF rendering and queued-route ownership remain distinct.

## Current original-first course

The ordinary four-case contract, caller and receiver were frozen and independently reviewed before execution or candidate inspection. The original source ran once, and all 45 original source, database, stream and process records were frozen before the candidate was inspected. The exact owner composition was independently reviewed before the same four cases ran once on the candidate.

Each case creates one fictional two-part SQLite project. `produce` is placed into a recorded running state, or into `outcome_unknown` for reconciliation; `consume` depends on it. No dispatch adapter is called. The blank reference consists of a space, a tab and another space. The ordinary reference is `"  file://fictional-artifact-東京-雪-é  "`. It is a label only and is never opened.

| API case | Actual original | Actual candidate |
|---|---|---|
| Direct completion, blank reference | Accepted; producer completed; consumer ready | `LedgerError`; producer still running; consumer blocked |
| Completed reconciliation, blank reference | Accepted; producer completed; consumer ready | `LedgerError`; producer still unknown; consumer blocked |
| Direct completion, ordinary Unicode reference | Exact reference retained; consumer ready | Exact reference retained; consumer ready |
| Completed reconciliation, ordinary Unicode reference | Exact reference retained; consumer ready | Exact reference retained; consumer ready |

Desired behavior improved from **2/4 to 4/4**. All eight API receiving child processes returned 0, were reaped, and did not time out. Those zeros mean each receiver completed its observation; they are not product CLI exit codes and do not turn the original blank-reference outcomes into passing behavior.

For both candidate refusals, the complete row, event list, project snapshot and whole database bytes are unchanged. For successful completions, the exact reference appears in the retained row, terminal event, fresh read-only API reopen and inspection report. The blocker report shows the expected blocked frontier or newly ready dependent. The writer is explicitly closed before the read-only window; whole database bytes and directory membership remain unchanged across that window. Actual timestamps are retained rather than normalized, so this receiving does not claim whole report bytes match across separate runs.

The original receiver preserved 14 input maps; the candidate preserved 56, including the 45 frozen original bodies. Both helpers and both actual outer processes completed with exit 0. Full raw stdout/stderr and process records are retained for all eight children. A five-second bound kills and reaps each direct child if needed; no descendant cleanup is claimed. The audit hook refuses sockets, child processes and writes outside the owned fixture, and admits SQLite connections only to that case's fictional database. This is a bounded trusted-fixture control, not an operating-system sandbox.

## Read the evidence

The [compact current status](current-receiving.json) binds both complete receipts, case outcomes, source identities and custody counts. The [pre-candidate source proof](pre-candidate-source-proof.json) preserves the exact source inverses and correctly retains its original `candidate_executed: false` checkpoint; completed results belong to the current status.

Full evidence is retained separately: the nine-module original and candidate source projections, four fictional databases per phase, raw observations, both unchanged owner tests, frozen criteria and process records. A separate delivery packet is prepared after source and receiving review. Packet integrity verification is data-only and must not replay the product. Retained drivers use historical absolute paths and are evidence, not generic replay commands.

This is a cloud public-API course. It makes no new inspect/blockers CLI, installed command, native host, browser, Hub, model-provider, real-ledger or scientific claim. No installed version was changed by this source integration.
