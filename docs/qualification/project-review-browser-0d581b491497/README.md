# Native browser receiving for the retained-project review

This contribution receives the existing draft [PR68](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/68), exact product head `429ca0db8e3ef2bfc511e08cd532ee67f79065d1`. It adds independent receiving material only. The original product, tests, guide and source-owner branch remain unchanged. Source owner `2a1c94fa2ecd/product_integration` retains adoption and main integration.

## Observed result

On the authorized MSI Windows 11 x64 host, CPython 3.14.3 and installed Microsoft Edge **154.0.4258.37** received an authored eight-part SQLite project through the actual native CLI and an isolated headless browser context. No dependency or browser download/install was performed. The browser used no personal profile or authenticated session.

| Course | Actual result |
| --- | --- |
| Nine CLI subprocesses | Expected statuses all matched: normal and actual Python -O creation, occupied output, database output, reserved WAL path, absent project, late malformed evidence, valid recovery and help. |
| Normal / optimized / recovery HTML | Exact identical 27,922 bytes; SHA-256 `be6e94f8df739b64eca41174fcdb4aa76877ba286317d22cbc5f4b9ac9d9c05e`. |
| Original frozen v1 receiver | **42 checks pass, 1 fails; exit 1.** This is retained without alteration. |
| Separate browser-only v2 continuation | **125 checks pass, 0 fail; exit 0.** No CLI rerun or product/oracle edit. |
| Actual browser download | Exactly the original 4,678-byte native inspection serialization, including its final LF; SHA-256 `f26828075eab772cf7cdb3209343e4ce4390aad4c7a5bd3677c4d41102896203`. |
| Source, oracle and existing HTML | Exact file identities remain unchanged. Inventories cover files, not an empty-directory census. |

The original receiver failed because it searched for the decoded evidence finding, including an actual newline, in the page's text. The page correctly displays structured evidence as JSON with an escaped newline. Inspection of the generated artifact established that representation mismatch. **It is a receiver-assumption failure, not a product failure or a silently revised pass.** V1 source, freeze, raw receipt, all 18 CLI output streams and its screenshot remain in the archive.

The separately versioned v2 continuation is explicitly generated-artifact-aware. It preserves the original expected values and checks the decoded JSON of every displayed native field. Its input HTML hash is bound to v1's successful normal and optimized outputs. It also checks the six numeric state counts; exact ready and blocked arrays; all 80 visible per-part fields; declaration-order table links; all eight full-object disclosures opened by keyboard; fragment navigation; the actual downloaded file; and identical text after moving and reopening the standalone HTML offline. Page-error monitoring is attached to both pages. No document HTTP request was observed.

The desktop screenshot independently shows counts completed=1, dispatching=1, failed=1, outcome_unknown=1, queued=3 and running=1; ready IDs `z_ready` and `c_ready_child`; blocked ID `a_blocked`. The 390-pixel screenshot and equal 390-pixel document scroll width are a narrow-viewport observation, not a full responsive or accessibility certification. Printing, screen readers, other browser engines and other OS/runtime combinations were not received.

## Oracle and source custody

The v1 receiver and authored inputs were frozen before the new renderer or its donor tests were read. Their source was the unchanged parent Ledger/inspection API at `6d76703f8a3d5a29e56bf9fab97523935b06e61c`, plus the public command and display contract. Hand-derived anchors independently checked the eight-part order, all six states, two queued-ready parts, one queued-blocked part and the ordered failed/unknown unmet prerequisites. Completed dependencies are excluded from the unmet list.

- Original receiver: 12,510 bytes / SHA-256 `08691a78840b622f5c9ed1e70646a060d73e81ff07101e66d139971c2defce15`.
- Oracle freeze: SHA-256 `edf50157f18bf8cdbf46dbe6780b2b19ad03da9b0c367488cdf881374572302e`.
- Browser continuation: 9,570 bytes / SHA-256 `f2df2ebda19b2a51e11420a37e5cfb7a6e96953efa523bd90f8ff01d167dc649`.
- V1 raw receipt: 15,621 bytes / SHA-256 `ce42be0a5dab76ad2b4a81d7bbd1396066b218127d0609764ae2532b7c802cf9`.
- V2 raw receipt: 20,024 bytes / SHA-256 `bbd5a60e78907ac88b9cc0cd1a1b2231544bbd4148fe115081bb5a4c2d143f5a`.

The native source projection contains the twelve exact Python package modules needed for this receiving, independently matched to the complete donor Git tree. It is not a full repository checkout. No maintained donor test was read or rerun for this independent course. The accepted source review already reported by PR68 remains separate.

`prepare_oracle.py` records original fixture construction. It requires an adjacent `original/` package projection matching `ORIGINAL-SOURCE.json`; that historical preparation is not needed to replay the saved oracle. The repository contribution retains the unchanged native receipts; the delivery contains all raw process outputs, images, actual downloaded bytes and source projection.

## Open the example and replay

The delivery's top-level `sample-review.html` is the exact received HTML. Open it as a local file. It depicts explicitly authored fixture state, not live estate tasks or externally verified work. Its download is the preserved native fixture snapshot. No server is required.

The immutable native archive is **268,250 bytes**, SHA-256 `e2d31c53e96368b753121630b0a5a00183ae3d85695c36dc28b631a22687229a`. It has 64 payloads plus `RESULT-MANIFEST.json`. The outer delivery also carries this guide, peer reviews and custody.

After extracting `native-results.zip` to a fresh `native` directory, this PowerShell invocation replays only the accepted browser continuation:

```powershell
python -B .\native\receive_browser_v2.py --candidate .\native\candidate --oracle .\native\oracle --html ".\native\receiving\received # % λ.html" --browser "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --out C:\receiving\new-browser-review
```

Use an existing installed Python Playwright and an explicit browser executable appropriate to the host. Choose a **new output path outside the candidate and oracle trees**. Do not create it in advance. The receiver inventories those input files before and after; it writes only its own new receiving directory.

To make a new example page from the exact retained fixture, run from `native/candidate` and choose a new output filename whose parent already exists:

```powershell
python -B -m fanout_engine.review --database "..\oracle\authored # % λ.sqlite3" --project browser-review --output C:\receiving\new-project-review.html
```

The v1 full receiver is retained for historical reproducibility and will encounter its documented representation assumption on this source. Use the v2 browser continuation for the corrected display-value comparison. The original no-module parent is an absent consumer, not a claimed original browser failure.

No source branch, live ledger, provider, adapter, recovery, reconciliation or installed production state was modified by receiving. Four admitted native process IDs reached terminal results: read-only preflight146484, original course142092, browser continuation114780 and export141784. The original course exited1 for its retained harness assertion; the other three exited0. Browser contexts were closed by their finally blocks.
