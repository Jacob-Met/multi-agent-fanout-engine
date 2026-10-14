# ThinkPad saved-inspection comparison with HTML

This dated adoption gives the existing `hamon-fanout-read` entry the maintained
`compare-inspections --format html` capability on **hamon-thinkpad, jacob,
UID/GID1000**. Staging and activation are separate operations. The source and
instructions alone do not establish that the active alias has changed: inspect
the accepted stage and installation receipts for the actual disposition.

## Use after accepted activation

Supply two existing saved inspection JSON files:

```sh
hamon-fanout-read compare-inspections \
  --first /absolute/path/to/first-inspection.json \
  --second /absolute/path/to/second-inspection.json \
  --format html --output /absolute/path/to/NEW-comparison.html
```

Open the resulting file directly in a browser. It displays literal saved
differences, complete First and Second documents, and a link containing the
exact native comparison JSON with its final newline. The static page has no
scripts, live controls, storage or external resources. First and Second mean
the supplied order, not authenticated chronology or permission to act.

Omit `--format html` for the unchanged default JSON. Omit `--output` to write
the selected format to stdout. Output files are create-only; an occupied
destination returns the maintained reporting failure and remains unchanged.
The route compares caller-selected saved files. It does not open a ledger,
dispatch work, reconcile uncertainty or contact a provider.

The six allowed routes are `projects`, `inspect`, `history`, `review`,
`blockers`, and `compare-inspections`. The first five keep their existing
literal dispatch statement and maintained parser behavior. Ledger readers
still require an explicitly selected existing database; no default ledger is
introduced. `dispatch` remains refused by the wrapper.

## Coherent source and installation

| Item | Exact boundary |
| --- | --- |
| Repository | Jacob-Met/multi-agent-fanout-engine |
| Complete maintained runtime source | `36f83e0767cf7088fc56cd04d07042f2b285c8d1` |
| Runtime source tree | `30a20d82623058cfd6dc86ffb92a0b502cc493ff` |
| Module closure | All 20 top-level `fanout_engine/*.py` files, explicitly listed in [source-manifest.json](source-manifest.json) |
| New private version | `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-36f83e0767cf-html-v1` |
| Existing alias | `/home/jacob/.local/bin/hamon-fanout-read` |
| Preserved previous target | `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1-compare-inspections-v2/hamon-fanout-read` |
| Interpreter | `/usr/bin/python3.14`, Python3.14.4 |
| Interpreter SHA256 | `52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41` |
| Operation/evidence directory | `/home/jacob/hamon-e1438c9d058f-installed-html` |

The new version is an honest **source installation**, not a rebuilt or upgraded
wheel. A fresh `venv --without-pip` uses the same qualified interpreter. The
exact 20 modules are copied into its otherwise empty private site-packages,
with a source manifest beside the wrapper. There is no pip operation, network
fetch, dependency installation or distribution metadata claiming a different
wheel. The wrapper executes this new version's fixed Python with `-I -B -m`;
system site-packages remain disabled.

The prior package at `639038bb09a14b54109efd2df2e699a22484a815` has 19 modules.
Eighteen module mode/blob tuples are identical to the new complete tree.
Only `compare_inspections.py` changes, to Git
`0c19318d482ee19540ee99e967567358cc96ae72`; the only added runtime file is
`compare_inspections_html.py`, Git
`8d861ce5fa279509b2478b8b2bff65e7f40ca46d`.
Every deployed module is nevertheless bound to the single complete new source
tree. Old package files, interpreter links, original wheel and metadata, all
prior wrapper versions and their owner receipts stay untouched.

The existing owner's [PR98 installation](../thinkpad-readers-c4c3dc26dd94/README.md)
and [PR102 blocker adoption](../thinkpad-blockers-c4c3dc26dd94/README.md) are
retained history. [PR104's wrapper-only comparison](../thinkpad-compare-inspections-e1438c9d058f/README.md)
remains the exact previous active target. This successor does not edit those
dated guides or replay their fixture/workflow courses.

## Retained observations and expected output

Receiving uses the already completed PR101 Windows180 authored retained-handoff
pair, copied with exact input identities into the operation directory:

| Input or output | Bytes | SHA256 |
| --- | ---: | --- |
| `inputs/first.json` | 3437 | `2d75e0a862db51fca8ae35697e18d884ed0ba9ac5988c241014e128fe8657150` |
| `inputs/second.json` | 4414 | `aa866b0a53cd0e911299c2c93b1f3339e537ac013e63fd25e0a041ba95d5302e` |
| Exact default comparison JSON | 12420 | `9d403925e7a6544e7f799fc05608383a339d34d11441c725119ac05575cbdb45` |
| Exact HTML projection | 48222 | `2eb35e0bd3c2a08e7472d24334425dec6e4f9468e11b9a2ab1e5e48a2b3abdf3` |

The result changes audit, summary and handoff; inventory and notes stay
unchanged. The recorded counts move from two completed/one unknown/two queued
to five completed. Audit retains a null task reference. These are authored
saved observations, not an estate-wide or live-state claim.

The exact HTML was already received at actual desktop/narrow widths through
normal-sandbox Chromium. Its retained V2 course has 21 successful checks and a
raw failure caused by an incomplete receiver Enter event. A separate reviewed
keyboard continuation passed14 checks, observed both native details opening,
and compared both full displayed documents. Four actual screenshots were
opened and accepted. The earlier Playwright dependency refusal and raw V2
failure stay distinct. Byte-identical staged HTML can reuse that evidence;
this adoption does not claim a new browser matrix or native download action.

The single inherited reader control is the prior nine-event direct-start
database, separate from the completed pair's execution:
`/home/jacob/hamon-e1438c9d058f-fanout-reader-closure/candidate-course/current-start-run/retained.sqlite3`.
The expected blocker stdout is526 bytes,
`b317b5b681261686f057597bf324e0e34685f387ab8ad5df7ddddc88d46c911e`.
It reports handoff blocked by unknown audit and queued summary, with summary
ready. The explicit database, three sidecar identities and native oracle are
preserved; no fixture, dispatch or workflow is rerun.

## Original refusal is preserved

Before implementation exposure, the existing installed entry was called once
with `--format html`. Native child704294 returned2 and was reaped, with empty
stdout, a plain unsupported-option diagnostic and no requested output.

The original receiver remains **raw FAIL8/9**, because it expected the program
label `compare_inspections.py`. Actual Python3.14 module invocation labels
help as `python -m fanout_engine.compare_inspections`. Its exact296-byte
stderr is SHA256
`9a4fb0c32b2f5367ae72404b5c3cbfafef03e0eceb66f01adc138c699161626e`.
The complete77323-byte receipt is
`80a22cc44789b38d753082447a903644a60ab055bd1430c47a264ca6d6fd7a7d`.
A separate read-only adjudication accepts the feature-absence observation,
preserving that reviewer mistake and all original bytes. Both observed PIDs
were absent afterward. The original command was not rerun.

## Staging, publication and activation

[install_html_reader.py](install_html_reader.py) is deliberately bound to this
account, admitted identities, exact source and retained observations. It is not
a general installer for another machine. Its required manifest, wrapper,
guide, raw original records, independent criteria and source projection must
be present at the recorded paths.

After source and receiving-controller review, one `stage` operation creates
the new version and records venv setup separately from nine product cases:

| Case | Required result |
| --- | --- |
| Default JSON | 0, exact12420 bytes, empty stderr |
| HTML stdout | 0, exact48222 bytes, empty stderr |
| New HTML file | 0, empty streams, exact complete file |
| Occupied HTML file | 1, clean reporting diagnostic, existing full identity preserved |
| Missing input | 2, no input/output created |
| Missing second argument | 2, plain native module-mode parser diagnostic |
| Dispatch | 2, exact six-route refusal |
| Wrapper help | 0, exact source help |
| Existing blocker observation | 0, exact526 bytes, empty stderr |

The version tree is captured after setup and preserved across the product
cases. The current alias, old runtime25 identities/package19 names, source
closure, raw history, retained inputs and caller environment are checked
before and afterward. The helper records streams and direct-child outcome
before evaluating success, and uses distinct observation and exported-file
names.

Stage failure preserves partial setup, raw streams and observed alias in
`stage-failed.json`; it does not clean the version or retry. Product calls
have15-second deadlines and one3-second post-kill wait; venv setup has60
seconds plus the same bounded collection. These limits concern direct
children, not process-tree containment.

Activation comes only after accepted stage evidence, independent review and
published-source readback. A same-directory temporary symlink is created and
the observed old alias is checked immediately before replacement. One actual
inherited-PATH HTML invocation then creates `installed/comparison.html` and
verifies its full expected bytes and embedded JSON. Old versions remain
available. The separately recorded installation receipt, not this guide,
establishes whether that operation completed.

These dated commands are phase entry points, not instructions to repeat a
completed phase:

```sh
/usr/bin/python3.14 -I -B \
  /home/jacob/hamon-e1438c9d058f-installed-html/candidate-source/install_html_reader.py stage
# Only after source/stage/publication review:
/usr/bin/python3.14 -I -B \
  /home/jacob/hamon-e1438c9d058f-installed-html/candidate-source/install_html_reader.py activate
```

## Recovery and withdrawal

The helper never automatically retries or rolls back activation. An
interruption or failed receipt write can leave a partial version, temporary
symlink or already changed alias. Inspect actual alias, raw command records and
failure record before deciding a next action. A missing success receipt does
not prove that no side effect occurred. Identity checks are ordinary
best-effort checks, not atomic compare-and-swap or hostile-race protection.

The source includes an explicit `withdraw` phase for a later deliberate
decision. It requires the exact installed alias and complete preserved version,
then creates a new symlink to the previous JSON-only PR104 target. It retains
both versions and records the new alias identity; it cannot restore the prior
inode. Withdrawal is not part of the stage or activation course and must remain
labeled **UNRUN** unless separately authorized and actually received.
