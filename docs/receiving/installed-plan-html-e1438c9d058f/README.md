# Read an installed plan comparison as an offline page

The installed `hamon-fanout-read` command can produce a self-contained HTML comparison of two authored plans. Open the resulting file in a browser to read the summary, both complete plans, their captured identities and every part's native idempotency key. Its download button carries the exact native comparison JSON, including the final newline.

```sh
hamon-fanout-read compare \
  --before before.json \
  --after after.json \
  --format html \
  --output comparison.html
```

Use an output filename that does not already exist, in an existing directory. The command publishes a new file exclusively. Open `comparison.html` directly from your file manager. The page is scriptless and contains its styles and JSON download; these features work offline. The file contains the supplied plan text, so share it with the same care as the plans themselves.

The input files use the maintained native plan format. See [the comparison guide](../../compare-plans.md) for the format, limits and comparison rules. The [installed reader receiving record](../thinkpad-plan-compare-e1438c9d058f/README.md) describes the wrapper that exposes this route on the ThinkPad.

## Read the result

**Summary** shows whether the native plans match, whether the project ID or complete part order changed, and which part IDs were added or removed. **Captured identities** gives each project's ID, native plan digest and raw input SHA-256. Raw input hashes can differ while the admitted native plans match—for example, when two JSON files use different formatting.

**Changed retained fields** presents directional changes from the before file to the after file. Both complete native plans remain visible below it. **Native idempotency keys** lists every after part, followed by removed parts. A key incorporates the complete native plan digest, so an unchanged part can receive a changed key when another part changes. This is an authored-plan review; execution state and permission to reuse a key are separate concerns.

Select **Download exact comparison JSON** to save `plan-comparison.json`. The page preserves the complete CLI report rather than reconstructing a smaller report from its visible fields.

## This receiving increment

This continuation belongs to HAMON team `e1438c9d058f`, following [PR116](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/116) and [PR117](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/117). Its reservation is [PR116 comment6175947069](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/116#issuecomment-6175947069). It uses the already installed HTML renderer and leaves the installed wrapper, runtime, alias and earlier results unchanged.

| Bound source or consumer | Identity |
|---|---|
| Installed runtime | `93c19c7fc74bda6652ab00a3d03266f53cbe5c1c` |
| Wrapper source merge | `124ea9d4c1ab4e01b86273d4d9550d3c5da7b6e0` |
| Active wrapper | `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-93c19c7fc74b-plan-compare-v1/hamon-fanout-read` |
| Receiving device | `hamon-thinkpad`, device `cadafaf3-4d0b-4c4f-a0d3-34a95d2cec90`, account `jacob` |
| Retained before input | 849 bytes; SHA-256 `453f3ffbcfe51321cf979fc45d41fdd46faf42a924307b0070821267c8af3e25` |
| Retained after input | 1,174 bytes; SHA-256 `888d78fcdf39217f87fd93ad54cf31ae833423a22d1c1f6632becf6451e8d22f` |
| Expected native JSON | 3,250 bytes; SHA-256 `107eb14f39b9a3e7175a538a1db5394f6f09d39e9a51bd225ee071f44fb0d9bb` |

The retained fictional sample has five parts: audit, inventory, notes, summary and handoff. Both files describe the same native plan, with digest `2c017159028c660378534ec1cb9f1f4bc25abbe2fb01820e0ed472b9c7d99a85`; their raw bytes differ. The frozen expectations contain both full plans, all three identity rows, all five complete keys and the exact native JSON. They were derived from the earlier independently accepted result before running this HTML course.

**Native receiving is accepted.** One ordinary installed HTML export passed all 18 receiving checks. Root independently parsed the actual page with a separate HTML parser and accepted 18 categories, including the complete plans, identity rows, five key rows and exact embedded JSON. The 14,854-byte HTML has SHA-256 `bcb395df29787ef114517f8e06db5e4ad12ec7ae0fd7396e9ef6cff0afb07a78`. The command returned 0 with empty stdout/stderr; both observed native process IDs were absent at postexit. All 112 protected identities, 64 inputs and 16 directory maps containing 1,145 entries were preserved.

**Browser receiving is accepted.** One fresh normal Chrome session on the identified MSI passed all 42 checks at 1,360 and 480 CSS pixels. Root independently accepted 14 categories and viewed both complete screenshots. Both views retain the full plans, all identity/key rows and the exact summary without horizontal clipping. One real clicked download produced the same 3,250-byte JSON. The sole page request served the exact accepted ThinkPad HTML; there were no page, request or cleanup errors. All 35 input identities, two directory maps and the configuration remained unchanged. The owning parent collected its Node child with exit 0, and all 14 tracked browser identities were absent at the final observations.

The browser course used Chrome 154.0.8037.97 on device `edc358ed-5ad6-4036-b7aa-8667bf0e14e0` (`MSI`, account `jacob`) with a task-owned fresh profile and loopback origin. Its full screenshots are 1,360 × 4,896 and 480 × 5,742 pixels. This is desktop Chromium viewport evidence; physical mobile input and a separate file-origin session were not tested. The profile is retained as receiving evidence. At narrow widths, long keys wrap into many short lines: all values remain present, and a separate layout improvement can make them easier to scan.

Portable delivery is recorded in the PR conversation and the existing Applications project record after fresh Drive download verification. The source and browser receiving are complete independently of that artifact handoff. The native comparator and prior browser courses were not rerun.

## Receiving sources and evidence

`receiving_common.py` reads file, link and directory identities. `freeze-native.py` re-admits the previous accepted installation and freezes this course's inputs. `receive-native.py` performs exactly one installed HTML export, saves its raw streams and process observation, then parses the actual HTML with Python's standard library. It checks the full plans, summary, identity and key rows, exact embedded JSON, and preservation of the installed state. Its direct child has a 15-second bound plus a three-second post-kill collection bound. `collect-native.py` performs read-only postexit checks.

These receiving helpers target the historical machine and task-owned paths recorded above. They are evidence of this finite receiving course, not a replacement CLI for ordinary use. A new receiving course needs a fresh namespace, current device admission and newly frozen configuration. The ordinary installed command at the top of this guide is the route for comparing another pair of plans.

The complete evidence package retains configuration, source input identities, raw outputs, exact process completion and independent reviews. The usable HTML and the browser's real JSON download are delivered separately from those records. The previous JSON export, inactive staging and alias activation courses are not repeated by this increment.
