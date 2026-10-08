# Independent native authored-plan preview receiving

**ACCEPT** for `fanout_engine/preview.py` Git blob `81e23c1269dc3d53a4c734ecd662e0f80d829eee`, SHA-256 `ee546965e5c95f165ad798e374847cc04f399afc067dfc1b62b06cc0edcf4029`, on original main `d65bde9c59b1d2593a80f6d838c0a40bf6768013` / tree `d5e5ad4e316be0b20a50151f8549ac490d3d99de`. The fresh main read after receiving still had these exact pins. This independent gate makes no publication, current-main integration or hosted matrix claim.

The eight-payload oracle was frozen before reading candidate source or author tests. Its unchanged original manifest is retained under `oracle/oracle-manifest.json` (SHA-256 `16adc942f823dbeb27d0c22df33d956e3366eb4c52447c722b59a6126a0a6909`). The reference uses only the accepted contract and original native normalization/routing rules; creating it ran no product process. The original two-process baseline and the author's distinct suite were not repeated.

## Actual native result

The unchanged oracle ran once on Python 3.12.14, using the exact five original native package modules plus the frozen new preview module. It ran **one native API process and seven actual `python -m fanout_engine.preview` processes**. Every case passed; all five refusals exited 2 with an ordinary diagnostic and no traceback.

| Receiving condition | Observed result |
|---|---|
| Native six-part consumer | Exact normalized plan, digest, all six idempotency keys and route objects; authored declaration order retained, including blocked parts. Initial readiness is exactly `scan, side`. Two explicit entries remain labeled explicit, including one equal to the ordinary pool route. |
| Native invalid overrides | Unknown part, non-Route value and unauthorized blocked last-part route refuse. Native Plan, router/catalog/pool, explicit mapping and configured step-up are unchanged; guarded database/socket/child/step-up effects do not occur. |
| CLI stdout | Exactly 2,115 UTF-8 bytes: native canonical JSON followed by one LF. Captured raw input hashes match independently frozen values; no timestamp/path/execution fields are added. |
| File output with stdout `/dev/full` | Success (exit 0), exact same 2,115 bytes published, no status write to stdout. |
| Unauthorized blocked last part | Exit 2, no partial report, destination or owned stage. |
| Malformed later part | Exit 2 before publication; prior valid parts do not create a partial report. |
| Destination symlink to plan input | Exit 2, original symlink and target bytes remain unchanged. |
| Kernel stage-write failure | `RLIMIT_FSIZE=512` makes the complete 2,115-byte report fail while staging; exit 2, destination absent, no owned stage remains. |
| Stdout `/dev/full` | Exit 2 with no shutdown traceback; no file delivery was requested. A general broken stream can deliver a prefix, so this does not claim all I/O failures imply zero delivery. |

The input files, an unrelated retained-owner marker, staged native source and original candidate/snapshot bytes, modes, inode and modification time remained unchanged. The source review separately confirms all fifteen candidate manifest entries, the eleven unchanged non-README original files and the exact original README prefix. It reads the new implementation's lazy validation, full-report serialization and publication/cleanup path; it does not infer provider authorization, capacity, dispatchability, stored execution state or service effects from configured routes.

## Evidence and replay

`receiving.json` is the exact executed receipt, SHA-256 `d1477ba7c3a3d71bb5151df7bd0412bd429949b7b56436e60f08c30815e62adb`. `native-artifacts.json` retains all 35 execution artifacts as content-addressed UTF-8 bodies, including each stdout/stderr, exact per-case raw inputs, actual file output, incremental events and receipt. Shared byte bodies are stored once. `native-command-result.json` preserves the real runner outcome. `source-review.json` and `current-main.json` retain the independent input/source fence. No source/test body is copied redundantly into this packet.

The author retains the one shared original source snapshot at `docs/qualification/plan-preview-0ee86eaeaf8d/original-twelve-files.json`, SHA-256 `ddd44fb5ba154e66c0950d754b70b34770038d0c726b4afd98379536b32ca53a`. From a checkout containing this evidence under `independent/`, the native replay is:

```sh
PYTHONDONTWRITEBYTECODE=1 HAMON_REVIEW_TMP=/dev python3 -B docs/qualification/plan-preview-0ee86eaeaf8d/independent/oracle/receive_preview.py --original docs/qualification/plan-preview-0ee86eaeaf8d/original-twelve-files.json --candidate fanout_engine/preview.py --candidate-sha256 ee546965e5c95f165ad798e374847cc04f399afc067dfc1b62b06cc0edcf4029 --output /path/to/new-receiving-directory
```

The chosen output directory must be absent. The Linux-specific receiving conditions use only the standard library, `/dev/full`, symlinks and `resource.RLIMIT_FSIZE`; they add no dependency or platform restriction to the product. The published workflow and current integration remain separate gates. The runner preserves any failed/interrupted attempt before raising and never edits owner source/caches. No additional unchanged native replay is required by this acceptance.
