# Receive the retained history reader

This example makes the existing history CLI reviewable against one retained native workflow. It preserves the exact source, database and reports needed to explain how a lost acknowledgement was later reconciled. It adds a receiving script and evidence guide; it does not change runtime modules.

The native course used accepted commit `6d76703f8a3d5a29e56bf9fab97523935b06e61c`, tree `831af49f435ba629c99c4ac6ab3ab0a1ecde58ce`. Keep that executed identity separate from the later commit that publishes this example and from subsequent main changes.

## Get the recorded input

[Download the verified receiving packet](https://drive.google.com/file/d/1MA6Mp798Qt47uuqoQQgssha0TZrCcj3z/view) — 73,357 bytes, SHA256 `f4cb59a292af0566961edd39db73e7e60118f6793c3b54ae1cb971cdced739ac`.

The outer packet contains the detailed guide, data-only verifier and unchanged inner archive `Fanout-Retained-History-6d76703-Native-20261013.tar.gz`:

- **51,302 bytes**; SHA256 `0fcd83ae30a52c959b6c8332e5cb5dd20b899c2df61ef5f607b481a0a6257a9b`.
- 28 payloads plus a manifest: exact command-specific source, original database copy, complete native stdout/oracles, raw receipts and review evidence.
- The database has 26 completed parts and 79 retained events. SHA256 `e17a509e8407d150ee9df3d80e24c6d4f99adaefb09534c8e9aa2bf4916a713d`.

Verify the inner archive without extracting or running its source, using this directory's verifier:

```sh
python verify_packet.py /path/to/Fanout-Retained-History-6d76703-Native-20261013.tar.gz
```

Extract the inner archive into a new directory. From its `source` directory, run the existing command:

```sh
python -B -S -m fanout_engine.history --database ../retained-workflow.sqlite3 --project native-dataset-review
python -B -S -m fanout_engine.history --database ../retained-workflow.sqlite3 --project native-dataset-review --part map-05
```

The source closure and database in the packet are sufficient for these commands. It contains nine runtime modules plus the maintained history guide, not the complete repository. The `inspect` helper imports `preview`, so that existing module is included. The history command supports an exact part filter; it loads the whole retained project history and has no paging option.

## Recorded outcome

One ThinkPad course on Python3.14.4 / SQLite3.46.1 ran those two CLI processes. Both exited0, with empty stderr and no timeout. Every output byte matched a separate direct `mode=ro` SQLite projection without importing the selected package. All source bytes, four stored tables, original database bytes and sidecars were preserved.

| Report | Events | Bytes | SHA256 |
| --- | ---: | ---: | --- |
| Complete project | 79 | 25,342 | `d0349a158f0511369550ac55ad3f79e559e95338fc0a476b6fcab3fc62c74889` |
| Exact `map-05` | 3 | 1,971 | `c4ac9373adbb517b6ce4986c0c3167e514ee7a37d9c30dda217092d03bf4514f` |

The `map-05` history has global sequence12 `dispatch_started`, sequence13 `outcome_unknown`, and sequence73 `reconciled` with verdict `completed`. The full workflow has 25 ordinary completed events and one explicit reconciliation. Each report preserves stored `detail_json` text and decoded `detail` values.

Sequence numbers describe recording order, not external execution order. The reconciliation retains an artifact path and SHA256 finding, but this history packet does not include that artifact or independently re-establish its effects. No work was dispatched, retried or reconciled in this reader course.

## Run the independent comparison

From the extracted inner archive root, choose a new output directory:

```sh
python -B receive_history.py --source source --database retained-workflow.sqlite3 --output fresh-history-review
```

The receiver pins the source manifest and original database, writes complete expected reports from direct SQL, invokes the public CLI twice and compares complete canonical stdout bytes. It retains partial timeout output and explicit failure receipts. Existing result directories are refused. All acceptance checks are explicit conditions, not Python `assert` statements.

The published receiver is byte-identical to the executed script, SHA256 `21f85e2d97cdf1201a5276759e346e12b40fdb634fbe4ebcf758d5045f690e17`. Use the packet's pinned source rather than assuming the current repository is the same composition. `QUALIFICATION.json` retains the exact native platform, commands, output hashes, preservation checks, independent review pin and limits. The enclosed course is already complete; the commands above start a new local observation only when intentionally invoked.

The maintained history implementation originated in [PR22](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/22) and was accepted through [PR30](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/30). See the [exact executed operator guide](https://github.com/Jacob-Met/multi-agent-fanout-engine/blob/6d76703f8a3d5a29e56bf9fab97523935b06e61c/docs/inspect-history.md) for the public contract.

This is one valid retained-ledger qualification. It adds no malformed-history, concurrent-writer, larger-history, alternate-platform, provider, installed-service or complete-suite claim. Private task-ID compositions and earlier performance experiments remain separate.
