# HAMON fanout plan identity review kit

This archive contains the complete source and qualification evidence from
[draft PR54](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/54) at
commit `000b1a0927b3864befb75f791f793991f5b53b5e`, tree
`35472226a5fe2b208e1fcee8d19efe49fe3e5fbf`. The coordinating owner retains
the main-branch integration decision.

The accepted product source is merge
`de72b62cac3f2d783691b7dfe39800e658b0800b`, tree
`7579c83e1dcc823d59b28bb19090d5d2c8e420a7`. It composes preview PR44,
ledger PR48 and dispatcher PR49 with the worker validation already present on
main `c86113dd09ff17d0c606b390b693caddb967f8b1`.

## Open and run

Extract the ZIP into an empty directory. `README_RECEIVING.md` and
`MANIFEST.json` are at the extraction root beside the repository's original
`README.md`, `fanout_engine/`, `examples/`, `tests/` and `docs/`.
There is no outer wrapper directory.

The project declares Python 3.10 or later and uses the standard library for its
local source entry points. No installation step is needed for the demo. From
the extraction root:

```sh
python3 -B examples/demo.py
```

Expected output:

```text
accepted research on worker-a at model-a/low
started: research
waiting on prerequisites: write
```

The demo uses its local adapter. See the original [README](README.md) for the
public API and the integration guides for preview, persistence, dispatch and
inspection.

## Source and manifest identity

All 228 repository files are byte-for-byte copies of the frozen Git tree.
The two generated files are this receiving guide and `MANIFEST.json`.
The manifest lists 229 payload files, including this guide and excluding the
manifest itself. The ZIP contains 230 regular relative file members.

Each manifest entry records its path, size and SHA-256. Repository entries also
record their original Git blob and mode. The archive preserves all repository
source, tests, guides and raw qualification evidence, including the exact
accepted component inputs. No working-copy bytecode or Git administration
directory is included.

The three maintained production blobs in the frozen source are:

| File | Git blob |
| --- | --- |
| `fanout_engine/preview.py` | `71dabb931a1adafd7ff449b53d3a1223e08e290d` |
| `fanout_engine/ledger.py` | `01c2f7845cad6f92152f797bbad8f4e791cc7273` |
| `fanout_engine/dispatch.py` | `bec8a82063dc06653128f155b8487428847b73c2` |

## Qualification and receiving limits

[Current source qualification](docs/qualification/plan-identity-current-main-37ede76e-20261013/README.md)
retains the actual 25 plan/native-key plus four worker test methods in normal
and optimized Python, the local demo, the complete admitted source manifest,
and independent 19-check static composition acceptance.

[Earlier three-repair qualification](docs/qualification/plan-identity-composition-37ede76e-20261013/README.md)
retains the complete 202-method run on its original source: 198 passes and four
macOS `/dev/full` skips. Those results keep their original source and runtime
scope. Neither this archive nor the later focused course establishes a Linux
result for the four skipped methods.

Historical receiving drivers keep their original native paths and inputs.
They document those executed courses. For work from a relocated extraction,
use the repository's regular entry points and maintained tests.

Independent package receiving and transport verification are supplied as
separate receipts alongside this unchanged archive. Source integration,
installed-worker adoption and provider submission remain separate decisions.
