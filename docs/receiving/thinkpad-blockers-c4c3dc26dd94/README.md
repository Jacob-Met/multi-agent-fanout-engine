# Installed Fanout blockers reader on ThinkPad

The existing `hamon-fanout-read` command on `hamon-thinkpad`, account `jacob`
(UID/GID/EGID 1000), now exposes the accepted `blockers` report. This dated
2026-10-14 adoption changes the small command wrapper only. It reuses the
qualified private Python environment and package already installed by
[PR98](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/98).

## Use the installed reader

Supply an existing saved Fanout database and the project identifier:

```sh
hamon-fanout-read blockers --database /absolute/path/to/saved.sqlite --project PROJECT
```

The fictional sample used during receiving remains available on this ThinkPad:

```sh
hamon-fanout-read blockers \
  --database /home/jacob/fanout-readers-20261013-c4c3dc26dd94/stage/authored-sample.sqlite \
  --project sample
```

Its exact 519-byte JSON report says `publish` is blocked by the recorded `draft`
(`running`) and `verify` (`outcome_unknown`) parts, in that order. `notes` is
queued and ready because its dependency is complete. These are fictional saved
states. The report does not dispatch work, infer a retry decision, or describe a
live queue. The sample database was read without modification.

The wrapper allows `projects`, `inspect`, `history`, `review`, and `blockers`.
Each route uses the package's existing parser and explicit database selection.
`blockers --project sample` refuses the missing `--database`; `dispatch` is
outside the allowlist. The existing blocker module also supports
`--output NEW.json` under its existing exclusive-output contract; this adoption
received stdout only and did not repeat the earlier export qualification.

## Exact installed and preserved versions

| Item | Identity |
| --- | --- |
| Installed alias | `/home/jacob/.local/bin/hamon-fanout-read` |
| New alias inode / device | `450635` / `66306` |
| New wrapper version | `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1-blockers-v1` |
| Wrapper Git blob | `9ecbb1dfc56bf2934ca9c77246b54ce8cf8fb0df` |
| Wrapper SHA256 / length | `39089b99978cb9786c1db4b1a075dccfcb97628aa7732657f976f0add17488fa` / 1,166 bytes |
| Preserved package version | `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1` |
| Qualified package source | `639038bb09a14b54109efd2df2e699a22484a815` |
| Blocker module Git blob | `8cdc09f08c7096ca5313ed80ed1cef0148bb977b` |
| Updater Git blob | `01bb916dc81a089f2b2ac4c98736d74e1d148337` |
| Native operation directory | `/home/jacob/fanout-blockers-20261014-c4c3dc26dd94` |

The new wrapper executes the old version's fixed `venv/bin/python -I -B -m`
route. The private interpreter links still resolve to `/usr/bin/python3.14`,
version 3.14.4, SHA256
`52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41`.
No wheel, package, interpreter, or venv upgrade occurred. Keep the old version:
the new wrapper depends on that exact environment.

The module was already accepted through
[PR85](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/85).
[PR59's owner handoff](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/59#issuecomment-6148132068)
records that disposition. Its complete body is unchanged here; the wrapper adds
one literal route and updates its help/refusal text. The previous four routes'
dispatch statement is unchanged. This is an installed entry-point increment,
not a new blocker algorithm or a replacement owner branch.

## What was received

The desired report and original refusal were frozen before the new wrapper.
The original actual inherited-PATH command exited 2 with empty stdout and the
old four-route refusal. Child `447718` was reaped without timeout; its outer
operation `447647` was observed at exit 0 because the witness receiver accepted
that original failure as the expected observation.

After full source review, the staged wrapper ran exactly three bounded cases:

| Stage case | Product outcome |
| --- | --- |
| Existing fictional database, project `sample` | Exit 0; exact 519-byte report; empty stderr |
| Missing `--database` | Exit 2; empty stdout; clean parser diagnostic |
| `dispatch` | Exit 2; empty stdout; exact five-route refusal |

The three children `460865`, `460866`, and `460867` were reaped without timeout.
The accepted local receiving helper recorded child `460860` at exit 0 and
receiver exit 0; outer `460793` was observed at exit 0. The alias still had its
old inode `450135` during all staged checks.

An independent review decoded all 25 stage-export bodies and compared full
integer-valued identities and raw streams before activation. The reviewed
updater then replaced only the admitted alias with a same-directory symlink to
the new wrapper. The separately bounded installed check invoked
`/usr/bin/env hamon-fanout-read ...` with the inherited environment (`env=None`).
Product child `463762` returned the exact report at exit 0 with empty stderr;
helper child `463761` and outer `463694` both completed at exit 0. All were
observed reaped/completed without timeout in their respective receipts.

Complete final read-only export retained 34 exact bodies, including all case
streams, phase receipts, helper markers, inputs and the new wrapper. Independent
review verified them against the earlier stage and actual final alias. The
original 25 qualified runtime file identities, saved database, interpreter
links, Python and historical receipt remain unchanged. Directory device,
inode, mode and ownership remain equal; directory mtimes are not promised
unchanged across deliberate creation of this new version.

The authored course, root's independent source/receipt reviews, and Delivery's
later packet integrity receiving are separate evidence. No old four-reader
matrix, blocker algorithm suite, live ledger, Hub/model call, remote provider,
or browser course was repeated. The helper and product timeouts bound direct
children; they do not claim process-tree or OS-sandbox containment.

## Preserved records and recovery

The packet retains the original refusal, exact expected report, first
unexecuted drafts, reviewed correction, completed native phase evidence and
connector initial/completion observations. A cloud-only metadata parser first
looked for `files` instead of the actual setup field `written`; that refusal
and its correction are retained. It caused no native setup or product replay.
Input setup itself was received once at outer `457043` exit 0. Read-only stage
and final exports `461314` and `464147` were also observed at exit 0.

The install source is [install_blockers_entry.py](install_blockers_entry.py).
The packaged command wrapper is a separate exact input, required alongside the
updater; this dated updater is bound to this account, source and old receipt.
It is not a general installer for another host. Receipt and stage paths are
exclusive; do not rerun a completed phase to obtain a cleaner transcript.

Withdrawal was source-reviewed and was **not executed**. On the recorded
ThinkPad, after inspecting the current alias and phase records, its guarded
entry is:

```sh
/usr/bin/python3.14 -I -B \
  /home/jacob/fanout-blockers-20261014-c4c3dc26dd94/install_blockers_entry.py withdraw
```

The updater requires its exact installed alias identity and unchanged original
runtime. It restores a newly created symlink to the old wrapper, records the
new symlink identity, and keeps both versions' bytes. It does not restore the
old inode. Existing switch/restore/withdrawal-record artifacts cause refusal.
Checks are ordinary best-effort identity checks, not atomic compare-and-swap
or hostile-race protection. Interruption or receipt-write failure can leave
transition artifacts or an already changed alias. Inspect actual alias and
failure records before any recovery; a missing success receipt alone is not
proof that activation or withdrawal had no effect.
