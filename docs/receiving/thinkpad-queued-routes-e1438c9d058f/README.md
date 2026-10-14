# ThinkPad queued-route reader adoption

This dated receiving recipe adds `queued-routes` to the existing `hamon-fanout-read` command on **hamon-thinkpad**, account **jacob**. It reuses the already qualified complete20-module HTML runtime from source commit `36f83e0767cf7088fc56cd04d07042f2b285c8d1`. It installs one small wrapper in a separate version directory. It does not create a virtual environment, install dependencies, replace runtime modules, or run a retained workflow.

The recipe belongs to [PR105's installed-reader follow-up](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/105#issuecomment-6161230923). [The preceding HTML adoption](../thinkpad-comparison-html-e1438c9d058f/README.md) remains the runtime and source-installation authority. This helper is bound to the admitted native files and exact account below; it is not a generic installer.

## Read an advisory queued-route report

After separately accepted activation, the ordinary installed command is:

```sh
hamon-fanout-read queued-routes \
  --database /home/jacob/hamon-e1438c9d058f-fanout-reader-closure/candidate-course/current-start-run/retained.sqlite3 \
  --project fixture-handoff-51df5b72e832 \
  --routes /home/jacob/hamon-e1438c9d058f-installed-queued-routes/inputs/routes.json
```

This prints the complete JSON report to stdout. The maintained module has no `--output` option. The selected ledger is an existing authored sample from a previous direct-start execution with nine events; this command only observes it.

For that exact observation, `summary` is ready and selects the `fixture-local` pool route at `low` effort. `handoff` remains blocked by `audit` in `outcome_unknown` and `summary` in `queued`. The report retains the stored plan digest and idempotency key and binds the supplied routing bytes by SHA256. It records two completed parts, one outcome-unknown part and two queued parts.

The result is advisory. It does not reserve or dispatch work, apply a routing choice, check worker availability or provider capacity, retry an attempt, or reconcile the audit. It preserves recorded uncertainty. SQLite may perform normal read-side WAL bookkeeping; this particular admitted ledger has no sidecars, and this receiving course requires those absent sidecars and all database bytes to remain unchanged.

All six existing reader routes remain available: `projects`, `inspect`, `history`, `review`, `blockers`, and `compare-inspections`. The latter retains JSON as its default and its HTML format. The wrapper continues to refuse `dispatch`.

## Exact native inputs and source boundary

The owned receiving directory is:

```text
/home/jacob/hamon-e1438c9d058f-installed-queued-routes
```

| Input | Bytes | SHA256 |
| --- | ---: | --- |
| Existing sample `retained.sqlite3` | 32768 | `975f735877fc15a4ee168806b0fbc65d368509bc716b793b0baebd03879cd113` |
| `inputs/routes.json` | 267 | `d421f5e5886d1a1fea9c50b862d311e882a66b23fb11c1ec5e359f926349ee22` |
| `inputs/expected-queued.json` | 1010 | `6364d6844f178fc8bf3e2e398abfa093a025082a741d53d7d44c99cba5d7133d` |
| `inputs/first.json` | 3437 | `2d75e0a862db51fca8ae35697e18d884ed0ba9ac5988c241014e128fe8657150` |
| `inputs/second.json` | 4414 | `aa866b0a53cd0e911299c2c93b1f3339e537ac013e63fd25e0a041ba95d5302e` |
| `inputs/expected-comparison.html` | 48222 | `2eb35e0bd3c2a08e7472d24334425dec6e4f9468e11b9a2ab1e5e48a2b3abdf3` |

The queued-route oracle is the exact prior native stdout, including final LF, from the same selected nine-event database and routing file. The HTML control uses the already received initial/final saved-inspection pair from the separate Windows180 course. These are two explicit consumer inputs; they are not presented as one execution.

Current-source admission used main `465232f1780ed1e8bfcff5417b54f1f7cc9d0b5f`, tree `271352ddd08da22d40451faeb80f52d0d947888d`. All20 runtime module blobs match that tree. Its only change from the preceding PR105 merge is removal of the workflow file; publication must preserve that removal and every unrelated leaf.

The maintained `fanout_engine/queued_routes.py` is unchanged:6197 bytes, Git blob `2e44069277cdb3298f2e07ad61b0869ba4f88256`, SHA256 `7515cdd5e49903a8a279eed8f093e265d54e707b0712e17230554135f085f17d`. The installed complete-source package remains rooted in the prior qualified source version; this wrapper addition does not relabel its package metadata or manufacture a wheel installation.

## Three source files and two operational phases

This directory publishes only:

- `hamon-fanout-read`: the wrapper, adding one literal mapping to `fanout_engine.queued_routes` and corresponding help/refusal text.
- `install_queued_reader.py`: a dated guarded helper with explicit `stage`, `activate`, and `withdraw` operations.
- This guide.

The wrapper's fixed execution boundary remains:

```sh
/home/jacob/.local/share/hamon-tools/hamon-fanout-read-36f83e0767cf-html-v1/venv/bin/python -I -B -m "fanout_engine.$route" "$@"
```

The new wrapper-only directory is:

```text
/home/jacob/.local/share/hamon-tools/hamon-fanout-read-36f83e0767cf-queued-routes-v1
```

The active alias before this recipe is `/home/jacob/.local/bin/hamon-fanout-read`, admitted inode453431, pointing at the preceding HTML wrapper. Stage requires that exact link and leaves it unchanged.

### Stage once, without activation

After source/controller review, use the canonical admitted interpreter:

```sh
/usr/bin/python3.14 -I -B \
  /home/jacob/hamon-e1438c9d058f-installed-queued-routes/candidate-source/install_queued_reader.py stage
```

The helper requires its exact original refusal, criteria, admission, source and all retained inputs. It refuses any occupied stage/version/result path. It creates one executable wrapper, then runs exactly five native commands against that inactive wrapper:

| Case | Required result |
| --- | --- |
| Queued-route report | Exit0, empty stderr, complete1010-byte oracle exactly |
| Missing required `--routes` | Exit2, empty stdout, clear ordinary parser diagnostic |
| `dispatch` | Exit2, empty stdout, exact wrapper refusal |
| Wrapper help | Exit0, complete expected help and empty stderr |
| Existing `compare-inspections --format html` | Exit0, empty stderr, exact48222-byte accepted HTML |

Each command has a finite15-second wait and, only following timeout, one bounded3-second collection after killing that direct child. Both streams are backed by exclusive files and retained before outcome predicates. A parent timeout is not proof of arbitrary descendant termination. The separate receiving observer records known process identities and refuses a successful lifecycle claim while an owned process remains.

The helper compares all admitted source/input/database/sidecar identities, complete retained-version membership, the new wrapper, and caller environment. Raw files and a successful `staged-receipt.json` are retained; a failure records `stage-failed.json` without cleanup or activation.

### Activate only after accepted stage and published source

Activation remains a separate action requiring current source and stage review. The helper verifies the unchanged accepted stage, exact old alias and existing runtime, creates its own temporary symlink, then replaces only the active alias. It executes one actual inherited-PATH queued-route command and compares its complete output with the frozen oracle.

```sh
/usr/bin/python3.14 -I -B \
  /home/jacob/hamon-e1438c9d058f-installed-queued-routes/candidate-source/install_queued_reader.py activate
```

Success leaves the actual report at `installed/queued-inherited.stdout.bin`, empty stderr, and `installation-receipt.json` with observed alias and preservation evidence. Stage and activation are distinct results. The source/guide bytes must remain unchanged between them because the accepted stage binds those files.

A failure after the atomic link replacement can leave the new alias active. The helper records the observed link and switch disposition in `activation-failed.json`; it never silently retries or rolls back. If transport fails, inspect the actual alias and existing receipts before any additional action.

## Recovery and evidence boundaries

An explicit, separately reviewed withdrawal is available only for the exact accepted installation:

```sh
/usr/bin/python3.14 -I -B \
  /home/jacob/hamon-e1438c9d058f-installed-queued-routes/candidate-source/install_queued_reader.py withdraw
```

It restores the previous HTML-capable wrapper target through a new symlink inode, preserves both wrapper versions and the entire shared runtime, and writes a withdrawal receipt. It does not run the workflow or delete outputs. Withdrawal is **UNRUN** in the receiving contract.

The original-only unsupported-route check ran once before this candidate was authored. It returned2, empty stdout and the exact103-byte prior-wrapper diagnostic, with12/12 characterization checks. All admitted state stayed unchanged and both observed processes were absent after collection. Its raw966309-byte receipt has SHA256 `2b2603836a632c043b7de7ba3a60d6f3367c1a6d45e3c8e18c47c1394c8b56c8`.

This guide is frozen before candidate stage and activation. Actual later status belongs to the separate native receipts, independent review, source-linked adoption note and final opening guide. It makes no new workflow, browser, provider or production-ledger claim. Exact HTML-byte parity reuses the existing companion's browser acceptance; no browser matrix is repeated.
