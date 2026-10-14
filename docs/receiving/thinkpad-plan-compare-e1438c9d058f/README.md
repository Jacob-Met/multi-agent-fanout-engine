# ThinkPad authored-plan comparison through the installed reader

This dated recipe adds the literal `compare` route to the already qualified
`hamon-fanout-read` wrapper on `hamon-thinkpad` for `jacob`. It uses the existing
complete 20-module source installation at commit
`93c19c7fc74bda6652ab00a3d03266f53cbe5c1c`, tree
`5d0f044ada289195eb427a0a7ba902adb977d61b`. It creates one new wrapper-only
version; it installs no runtime, module, dependency or interpreter.

The useful input pair is the actual 849-byte native plan exported in
[the installed export-plan receiving](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/115#issuecomment-6164134503)
and the original 1,174-byte authored sample plan. They encode the same five-part
plan despite different input bytes and formatting. The complete 3,250-byte
comparison reports `same_plan: true`, unchanged project/order, no added,
removed or changed parts, and the same native keys for all five parts.

## Use the reader after the separately accepted activation

Choose explicit local files and an unused output path:

```sh
hamon-fanout-read compare \
  --before recorded-plan.json \
  --after authored-plan.json \
  --output new-comparison.json
```

Without `--output`, the command writes its native JSON to stdout. A completed
file export leaves stdout and stderr empty and returns zero. An occupied output
returns one and preserves the existing file. The maintained command also
supports `--format html`; this recipe qualifies only native JSON. The previous
[authored-plan renderer qualification](../../compare-plans.md) remains separate,
and this receiving performs no HTML rendering or browser course.

`compare` describes authored plan content. It does not compare saved execution
state, read a ledger, authorize task reuse, or dispatch, retry or reconcile work.
Use `compare-inspections` for the separately maintained saved-inspection
comparison. An exported plan is not a ledger backup. Matching keys and plans do
not grant permission to replay work or import a ledger.

## Exact retained pair

| File in this receiving workspace | Bytes | SHA-256 |
|---|---:|---|
| `inputs/before.json` | 849 | `453f3ffbcfe51321cf979fc45d41fdd46faf42a924307b0070821267c8af3e25` |
| `inputs/after.json` | 1174 | `888d78fcdf39217f87fd93ad54cf31ae833423a22d1c1f6632becf6451e8d22f` |
| `inputs/expected-comparison.json` | 3250 | `107eb14f39b9a3e7175a538a1db5394f6f09d39e9a51bd225ee071f44fb0d9bb` |

The before file is the actual installed export from PR115. The after file is the
original fictional retained-handoff plan. The comparison oracle is the actual
PR115 native comparison, independently reconstructed from the complete plan
objects and native key framing before this candidate was authored. Its digest
is `2c017159028c660378534ec1cb9f1f4bc25abbe2fb01820e0ed472b9c7d99a85`.
The ordered parts are `audit`, `inventory`, `notes`, `summary`, `handoff`.

One existing-route control reads the already produced direct-start sample ledger
and must export those same 849 bytes. That genuine earlier execution contains
nine events. This recipe creates no new workflow and does not relabel the
separate full-run ledger as the same execution.

## Source and authority

The three additive files in this directory are the wrapper, the dated
`install_plan_compare_reader.py` helper and this guide. They preserve the eight
previous route statements and fixed private-interpreter exec. The only new
dispatch is literal `compare → compare`; no caller-selected module name or
evaluated command is introduced.

The new wrapper retains `export-plan`, `queued-routes`,
`compare-inspections`, `projects`, `inspect`, `history`, `review` and
`blockers`. Other words continue to receive the wrapper's exit-two refusal.
The existing private Python entry resolves to the admitted canonical
`/usr/bin/python3.14`, version 3.14.4, and executes with `-I -B`.
All 20 installed modules and every prior version remain unchanged.

The dated source paths are:

- Receiving workspace: `/home/jacob/hamon-e1438c9d058f-installed-plan-compare`.
- Fixed runtime: `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-93c19c7fc74b-queued-output-v1`.
- Previous wrapper: `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-93c19c7fc74b-export-plan-v1/hamon-fanout-read`.
- New wrapper-only version: `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-93c19c7fc74b-plan-compare-v1`.
- User alias: `/home/jacob/.local/bin/hamon-fanout-read`.

The helper is a pinned receiving recipe for this admitted device and workspace,
not a portable installer. It requires the native admission, frozen criteria,
static characterization, input copies and exact candidate sources. Do not
retarget its constants or substitute a different runtime and then claim these
receipts. The fixed runtime's independent installed-output receiving is retained
in [PR114](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/114#issuecomment-6163201973).

## Original limitation: static characterization, no native course

The original 2,076-byte wrapper was read in full and bound by byte hash. Its eight
literal cases contain no `compare` dispatch; the default branch prints its
131-byte usage diagnostic to stderr and exits two. That describes the source
boundary, not an observed native invocation. The proposed original command was
omitted before candidate exposure and remains **UNRUN**. The earlier reservation
is preserved with its explicit
[scope amendment](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/74#issuecomment-6164293472).
No synthetic receipt is presented as a native refusal.

At this source freeze, the inactive stage, activation and withdrawal are also
**UNRUN**. Actual outcomes belong to separately sealed receiving records and
source-linked adoption notes; this source-bound guide is not edited between
stage and activation.

## Inactive stage: four finite native commands

Run the helper only after the exact source and outer controller/config gate.
The helper's `stage` phase admits the host/account, canonical interpreter,
current alias inode 453397, complete runtime and previous-version identities,
all retained input bytes and the static original authority. It requires fresh
version and stage destinations, creates the wrapper-only version, and invokes:

1. The new wrapper's default `compare --before inputs/before.json --after inputs/after.json`: exit zero, exact 3,250-byte stdout, empty stderr.
2. The same command with `--output stage/exported-comparison.json`: exit zero, empty stdout/stderr, the same complete JSON file.
3. The same explicit output again: exit one, empty stdout, exact occupied-output diagnostic and unchanged file identity.
4. The new wrapper's existing `export-plan` route against the admitted sample ledger/project: exit zero, exact 849-byte stdout and empty stderr.

The filename `exported-comparison.json` is distinct from every process
observation filename. Each native command has a 15-second wait and, only after a
timeout, one bounded three-second collection after killing that direct child.
The outer observer separately bounds the helper to 120 seconds plus one
five-second collection. Raw stdout, stderr and process records are written
before acceptance predicates. A failed or unreaped observation stops later
commands. These limits do not prove termination of unobserved descendants.

A passing stage preserves the active alias, all old versions and modules,
interpreter/link identities, saved documents, original ledger and three sidecar
identities, complete input and source membership, and caller environment.
It records all 13 native stage files plus the new wrapper identity. It does
not activate the new wrapper.

## Guarded activation and actual inherited-PATH use

Activation needs accepted stage bytes, published exact three-file source,
remote tree review, merge evidence and a separate explicit activation gate.
The helper checks the original alias and all admitted inputs again before its
single replacement. It prepares a separate symlink, checks that link and the
old alias, then replaces only the public alias. All old version directories
remain intact.

The activation consumer is one actual inherited-PATH command:

```sh
/usr/bin/env hamon-fanout-read compare \
  --before /home/jacob/hamon-e1438c9d058f-installed-plan-compare/inputs/before.json \
  --after /home/jacob/hamon-e1438c9d058f-installed-plan-compare/inputs/after.json \
  --output /home/jacob/hamon-e1438c9d058f-installed-plan-compare/installed/comparison.json
```

Its complete 3,250-byte output must equal the frozen native oracle, with exit
zero and empty stdout/stderr. The activation observer records the actual alias,
native process result, full output and unchanged runtime/source/input state.
It does not rerun the four staging commands.

A failure after replacement may leave the new alias active. The helper records
the actual alias and whether replacement returned; it performs no automatic
rollback, retry, cleanup or second activation. If a connector result is
ambiguous, inspect the retained process and actual alias before any further
action. A missing reply is not evidence that the replacement did not occur.

## Explicit withdrawal remains a separate operation

The `withdraw` phase is provided for separately reviewed recovery. It requires
the accepted installed receipt, exact current alias, untouched stage inputs and
new wrapper. It prepares and checks a separate restoration symlink, then
replaces the alias once with a new symlink to the preserved previous eight-route
wrapper. It removes no runtime or version bytes. Withdrawal is **UNRUN** at this
checkpoint; no recovery qualification is inferred from stage or activation.

The source recipe and raw evidence retain their actual scopes. Previous
authored-plan HTML/browser results, installed saved-inspection HTML,
queued-route output and export-plan receiving remain separately linked records.
