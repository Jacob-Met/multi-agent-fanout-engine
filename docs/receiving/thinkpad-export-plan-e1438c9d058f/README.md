# ThinkPad native plan export

This dated recipe exposes the maintained `export-plan` reader through `hamon-fanout-read` on **hamon-thinkpad**, account **jacob**. It adds one small wrapper in a separate version directory and reuses the complete pinned **93c19c7fc74b** source installation received in [the queued-file adoption](../thinkpad-queued-output-e1438c9d058f/README.md). It does not install or replace runtime modules, create an environment, or replay a retained workflow.

The maintained exporter and its historical qualification belong to [PR86](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/86). This installed-consumer scope is [reserved separately](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/86#issuecomment-6163303867). See [Export a recorded native plan](../../export-recorded-plan.md) for the general API, parser and publication contract. The old wheel/example kit remains unchanged.

## Export a recorded plan

After separately reviewed activation, select an existing ledger and a fresh destination:

```sh
hamon-fanout-read export-plan \
  --database /home/jacob/hamon-e1438c9d058f-fanout-reader-closure/candidate-course/current-start-run/retained.sqlite3 \
  --project fixture-handoff-51df5b72e832 \
  --output /home/jacob/recorded-handoff-plan.json
```

Choose another destination if that file already exists. Omitting `--output` writes the complete native JSON and final newline to stdout. Exit0 means the write completed; exit2 means argument or selected-plan reading/validation failed; exit1 means output publication failed after the plan was read. An occupied file, the database or a reserved SQLite sidecar destination is refused by the unchanged maintained publication rules.

The sample is an already-produced direct-start observation with nine events. The exported document contains only authored project and part data: identifiers, exact instructions, ordered dependencies, tags and authored part order. It does **not** contain runtime states, task or worker identifiers, routes, evidence or history. It is not a restorable database backup. Exporting does not record a new plan, dispatch work, resolve uncertainty, or authorize reuse of execution keys.

The five parts are `audit`, `inventory`, `notes`, `summary` and `handoff`. This sample's complete canonical export is **849 bytes**, including LF, with SHA256 `453f3ffbcfe51321cf979fc45d41fdd46faf42a924307b0070821267c8af3e25`. Its plan digest is `2c017159028c660378534ec1cb9f1f4bc25abbe2fb01820e0ed472b9c7d99a85`.

## Use the exported file

The existing native comparison command can consume an export and a separately authored proposal. This wrapper addition exposes only `export-plan`; it does not add a general module launcher or a `compare` wrapper route. On this exact installation, the retained comparison consumer can be invoked explicitly:

```sh
/home/jacob/.local/share/hamon-tools/hamon-fanout-read-93c19c7fc74b-queued-output-v1/venv/bin/python -I -B \
  -m fanout_engine.compare \
  --before /home/jacob/recorded-handoff-plan.json \
  --after /home/jacob/proposed-handoff-plan.json \
  --output /home/jacob/handoff-plan-comparison.json
```

Keep the original export and edit a separate proposal. The comparison describes authored plan identity and differences; it does not adopt a proposal into the ledger. Its parser retains its own limits and tag normalization. Directly constructed native plans may contain repeated or differently ordered tags that the comparison parser normalizes. The received sample has sorted unique tags and qualifies the ordinary compatible path.

All seven existing wrapper routes remain unchanged: `projects`, `inspect`, `history`, `review`, `blockers`, `queued-routes` and `compare-inspections`. Their source and prior qualification remain attributed to the existing installation. This increment does not repeat their courses. The wrapper still refuses unlisted commands, including dispatch.

## Exact source and inputs

The owned receiving directory is `/home/jacob/hamon-e1438c9d058f-installed-export-plan`. The runtime remains the entire20-module source projection at commit `93c19c7fc74bda6652ab00a3d03266f53cbe5c1c`, tree `5d0f044ada289195eb427a0a7ba902adb977d61b`. It is an exact source installation, not a latest-main or wheel-version claim.

The exporter is unchanged: `fanout_engine/export_plan.py`,2475 bytes, Git blob `6d3e4dabe00507e1d537f332941f35c2f2f6a5bf`. Every installed module is checked against the preceding source manifest. No new runtime closure is composed.

| Admitted input | Bytes | SHA256 |
| --- | ---: | --- |
| Existing sample retained.sqlite3 | 32768 | `975f735877fc15a4ee168806b0fbc65d368509bc716b793b0baebd03879cd113` |
| inputs/authored-plan.json | 1174 | `888d78fcdf39217f87fd93ad54cf31ae833423a22d1c1f6632becf6451e8d22f` |
| inputs/expected-plan.json | 849 | `453f3ffbcfe51321cf979fc45d41fdd46faf42a924307b0070821267c8af3e25` |
| inputs/expected-comparison.json | 3250 | `107eb14f39b9a3e7175a538a1db5394f6f09d39e9a51bd225ee071f44fb0d9bb` |
| inputs/initial-inspection.json | 3438 | `6355cde2c4866966581cb8db4b5b3ffb637a5c3ba26d598973de75e58a94f6e1` |

The authored fixture is Git blob `a4be5c7ddc62499daf5d3577695a48980be28f0f`. Pure-data admission expands omitted empty dependency arrays and independently checks every authored record, digest and native key against the saved initial inspection. The reviewer independently derived the same full export and comparison before candidate exposure. No product import or ledger read created these expected bytes.

The selected ledger and its three absent sidecars are pinned. The receiving course requires their bytes, metadata and absence to remain unchanged. The general reader still follows SQLite's ordinary snapshot and read-side bookkeeping behavior; this evidence does not promise that arbitrary WAL deployments never create sidecars.

## Guarded phases

This directory publishes three files: the wrapper, `install_export_plan_reader.py`, and this guide. The helper is bound to the exact host, account, paths, criteria and original refusal. It is a dated receiving recipe, not a generic installer.

The existing alias is `/home/jacob/.local/bin/hamon-fanout-read`, admitted inode453409. It targets the preceding queued-output wrapper. The candidate directory is `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-93c19c7fc74b-export-plan-v1`; it contains only the new wrapper. The fixed execution boundary continues to use the existing private Python with `-I -B`.

After source and observer review, stage once:

```sh
/usr/bin/python3.14 -I -B \
  /home/jacob/hamon-e1438c9d058f-installed-export-plan/candidate-source/install_export_plan_reader.py stage
```

Exactly four real commands are required:

| Case | Required result |
| --- | --- |
| Native stdout export | Exit0, empty stderr, exact849 bytes |
| New file export | Exit0, both streams empty, exact849-byte stage/exported-plan.json |
| Occupied export | Exit1, exact native refusal, existing file identity retained |
| Existing compare consumer | Exit0, empty stderr, exact3250-byte report against original1174-byte authored input |

The comparison must report the same plan, no changed fields, no added or removed parts, and all five unchanged keys, while retaining the different exact input-file hashes. Source, complete old-version membership, runtime, database/sidecars, alias and selected inputs remain pinned through stage.

Each native command has a15-second wait. Only on timeout, its direct child is killed and collected for at most3 seconds; raw file streams and process observations are recorded before receiving assertions. A failure stops the remaining commands, preserves partial files and produces a failure receipt. Parent termination is not proof of arbitrary descendant termination. The outer observer separately records and verifies all observed process identities. There is no automatic retry, cleanup or activation.

After accepted stage and published-source review, activation is separately authorized:

```sh
/usr/bin/python3.14 -I -B \
  /home/jacob/hamon-e1438c9d058f-installed-export-plan/candidate-source/install_export_plan_reader.py activate
```

It verifies the exact old alias and accepted stage, replaces only that alias through an owned temporary link, then runs one actual inherited-PATH file export. Success leaves `installed/recorded-plan.json` and `installation-receipt.json`. The source and authority bindings and source/guide bytes remain unchanged between stage and activation. A failure after replacement can leave the new alias active; the helper records the actual alias and switch disposition, without automatic rollback. Inspect the retained state after an uncertain transport result before any further action.

An explicit, separately reviewed `withdraw` operation is provided for the exact accepted installation. It restores the previous target using a new symlink inode, retains both versions and the unchanged runtime, and records its result. It runs no product command and deletes no version.

## Qualification checkpoint

The original unsupported-route call completed once before candidate authoring: exit2, empty stdout, exact118-byte old-wrapper diagnostic, no requested file or candidate version. Native8 checks and independent12 predicates accepted conservation; both observed processes were absent after collection. Its full1070003-byte receipt is SHA256 `da5bb552f319c3adeae5640c20ab0121ea2e34da23c24222fa04c8a2cc318b84`.

This source guide is frozen while **stage, activation and withdrawal are UNRUN**. Later actual results belong to separate receipts, the source-linked adoption note and the opening guide; these source bytes are not rewritten to change historical status. No new workflow, browser, provider or production-ledger qualification is claimed.
