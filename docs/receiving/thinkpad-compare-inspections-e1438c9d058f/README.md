# Saved-inspection comparison entry for the ThinkPad reader

This dated wrapper adds `compare-inspections` to the existing
`hamon-fanout-read` command on hamon-thinkpad, account jacob. It uses the
JSON comparator already present in the qualified private package. The package,
wheel, interpreter, modules and prior wrapper versions remain unchanged.

Staging and activation are separate. The source files alone do not establish
that the active alias has changed: inspect the installation receipt and alias
for this version before using the new entry.

## Read the saved comparison

After the separate activation succeeds, the public command is:

```sh
hamon-fanout-read compare-inspections \
  --first /absolute/path/to/first-inspection.json \
  --second /absolute/path/to/second-inspection.json
```

It prints the complete native JSON report. To retain it, add
`--output /absolute/path/to/NEW-comparison.json`; the existing publisher refuses
an occupied output path. This installed module is JSON-only and has no
`--format` option. Later repository HTML features are not installed by this
wrapper addition.

The actual receiving pair is already saved under:

```sh
hamon-fanout-read compare-inspections \
  --first /home/jacob/hamon-e1438c9d058f-installed-comparison/inputs/first.json \
  --second /home/jacob/hamon-e1438c9d058f-installed-comparison/inputs/second.json
```

These are byte-exact copies of the initial and final inspections from the
accepted PR101 Windows180 authored retained-handoff run. They describe changes
to `audit`, `summary` and `handoff`; `inventory` and `notes` are unchanged.
The initial saved counts contain two completed parts, one unknown outcome and
two queued parts; the final saved counts contain five completed parts. Audit's
task reference remains null. The complete prior comparison is 12,420 bytes,
including final LF, SHA-256
`9d403925e7a6544e7f799fc05608383a339d34d11441c725119ac05575cbdb45`.

The comparator reads these JSON files without opening their ledger or rerunning
work. It describes saved values, preserving full documents and their raw input
identities. Its First/Second labels do not authenticate chronology or authorize
dispatch, retry or reconciliation; the known same-run provenance comes from
the earlier native receiving evidence.

## Preserved installation and exact route

| Item | Identity |
| --- | --- |
| Active command alias | `/home/jacob/.local/bin/hamon-fanout-read` |
| Previous wrapper | `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1-blockers-v1/hamon-fanout-read` |
| New version directory | `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1-compare-inspections-v2` |
| Preserved private package | `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1` |
| Package source | `639038bb09a14b54109efd2df2e699a22484a815` |
| Existing comparator Git blob | `d0cee2336eec6bdb87b05877af70c0d30dea0b8c` |
| Existing comparator SHA-256 | `97ce5cadedbfcb935515dee4acdf7d1fb04a7a25c8e8b802b2b6138c820d31a4` |
| New wrapper SHA-256 / length | `9c94ad1ceae16cbba8104b4b557a32a3232075076a81d679f07e2062b0162c5e` / 1,426 bytes |

The single literal spelling `compare-inspections` maps to
`fanout_engine.compare_inspections`. The five prior route statements
(`projects`, `inspect`, `history`, `review`, `blockers`) and the fixed
`venv/bin/python -I -B -m` execution remain unchanged. The private interpreter
resolves to the admitted `/usr/bin/python3.14`, version 3.14.4.
The old PR102 owner-qualified version is retained; its
[opening guide](../thinkpad-blockers-c4c3dc26dd94/README.md) still describes that
version. Ownership and the additive source scope are coordinated in
[PR102's reservation](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/102#issuecomment-6158731352).

## Guarded native phases

[install_compare_entry.py](install_compare_entry.py) is a dated helper bound to
this account, installed identities, preserved inputs and original refusal. It
is not a general installer for another host. The exact sibling
[hamon-fanout-read](hamon-fanout-read), this guide and the pinned admission,
criteria, original raw receipt/streams and independent original review are
required in the recorded native operation directory.

The original named-command invocation was received before candidate exposure:
product exit 2, zero stdout and the exact 82-byte five-route refusal. Its
receiver recorded nine characterization checks; independent review accepted
eleven predicates. This original outcome remains a refusal, not evidence of
the new capability.

The first stage was refused after its complete stdout comparison succeeded:
the helper had used `stage/comparison.json` for both an observation record and
the requested export. The product correctly refused that occupied path. Its
raw FAIL, prior candidate source, partial version and stage files are retained.
This corrected helper uses fresh V2 paths and a distinct export filename; it
does not overwrite or relabel those earlier observations.

On the recorded host, each phase is an explicit separate command:

```sh
/usr/bin/python3.14 -I -B \
  /home/jacob/hamon-e1438c9d058f-installed-comparison/candidate-source-v2/install_compare_entry.py stage
```

Stage creates a fresh version and six bounded native observations: complete
stdout comparison, new-file export, occupied-file refusal, missing second input,
forbidden dispatch and help. Actual stdout/export bytes must match the complete
prior oracle. The occupied control must leave the newly exported report's full
identity unchanged. Stage checks all preserved installed identities, complete
package membership, input copies/originals and source files; the active alias
remains the admitted five-route alias. A successful stage writes
`staged-v2-receipt.json`. Observation records use names such as
`stage-v2/comparison.json`; the native exported payload is separately named
`stage-v2/exported-comparison.json`.

After source and stage receiving are independently accepted, activation is:

```sh
/usr/bin/python3.14 -I -B \
  /home/jacob/hamon-e1438c9d058f-installed-comparison/candidate-source-v2/install_compare_entry.py activate
```

Activation rechecks the exact old alias, staged version, preserved runtime and
raw stage evidence. It creates a same-directory temporary symlink and replaces
only the approved alias, then receives one actual inherited-PATH comparison
with the unchanged full oracle. A successful `installation-receipt.json`
records the new alias identity. The old alias inode is intentionally replaced;
old wrapper/package bytes remain unchanged. No package manager or interpreter
upgrade runs.

Each observation retains raw stdout/stderr/status before acceptance. The
receiver uses a 15-second direct-child wait and a separate three-second
post-kill collection ceiling. These are bounded direct-child observations,
not a process-tree or OS-sandbox containment claim.

## Failure records and explicit withdrawal

Existing version, stage, switch, installed or withdrawal records cause refusal;
do not rerun a completed or uncertain phase to obtain a cleaner transcript.
Stage failure can leave a partial new version but does not activate it.
Activation can change the alias before a later observation or receipt write
fails. The helper records its observed state when possible and does not retry
or automatically roll back. Inspect the actual alias, version bytes and raw
phase records before deciding the next action. A missing success receipt does
not prove that no alias change occurred.

The separately guarded withdrawal entry is:

```sh
/usr/bin/python3.14 -I -B \
  /home/jacob/hamon-e1438c9d058f-installed-comparison/candidate-source-v2/install_compare_entry.py withdraw
```

It requires the exact accepted installed alias and unchanged runtime/version,
then creates a new symlink to the retained PR102 five-route wrapper. It records
that new inode and keeps all version bytes. Withdrawal is not implicit in any
other phase and must not be inferred as executed from source review.

All identity guards are ordinary best-effort checks, not atomic
compare-and-swap or hostile-race protection. An interruption or write failure
during switching/withdrawal requires observing the actual alias before any
further action.
