# Read-only CLI stdout receiving

The receiving helper in this guide exercises the output contract repaired by [PR80](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/80). It calls the real `preview`, `inspect`, `history` and `projects` command entry points using owned synthetic inputs.

## Recorded result and source

| Course | Source | Result |
|---|---|---|
| Corrected original controls | `ad99d83d23e029cc383b2adf8a999f23be642f8c` | 22 checks passed, four missing-stdout checks failed; 23 actual CLI children |
| Unchanged corrected receiver against the repair | `ac975099c9d03b5ca106ab9a30e00a5872e58fc6` | 26/26 checks passed; 23 actual CLI children |

Both complete courses used ordinary Python 3.12.14 on cloud Linux. All children exited naturally, with no forced signals and no remaining owned process group. Source, oracle, expectations and retained inputs preserved their recorded bytes, modes and modification times. A separate outside-oracle check also preserved all twelve offered candidate runtime, maintained-test and guide files.

The original commands all emitted an AttributeError traceback when Python started with descriptor 1 closed. Authored preview returned 1 instead of its existing handled output-refusal code 2. Inspect, history and projects returned their expected code 1 but failed the useful single-diagnostic requirement. The repair adds a small missing-stdout guard to the two shared writer implementations and passes the unchanged receiving course.

PR80 merged as `dfa1ebbf2c2d5bea880cb4f37898ca4109aed4c2`, with exact received tree `795625dc75232992cd281eac6d7c3f0442c208a8`. Its parents are the original baseline and received head above. The paired artifact froze against the draft head; the later merge has the same tree.

| Repaired module | Received SHA256 |
|---|---|
| `fanout_engine/preview.py` | `063c79e3213d1b00864c27832e4ac667c0c58978b13173a746359eedebdc5de5` |
| `fanout_engine/inspect.py` | `7c72c0a953e84a805a12a2230f398b1271947a3c4db8d19d805cad785b440111` |

The eight other modules in the executed import closure remain byte-exact to the original. The public source scope and output contract were recorded in [the ownership comment](https://github.com/Jacob-Met/hamon/issues/143#issuecomment-6144101879). No routing, ledger transition, report schema, dispatch, provider or output-path behavior is added by this repair or these receiving files.

## Active exact pair

Use these two siblings together:

- `tools/receiving/readonly-stdout/receive-readonly-stdout-v3.py`
- `tools/receiving/readonly-stdout/stdout-expectations-v2.json`

The helper takes these positional arguments:

```text
SOURCE_ROOT NEW_OUTPUT original
SOURCE_ROOT NEW_OUTPUT candidate ORIGINAL_CONTROL_DIRECTORY
```

The source root must contain the intended `fanout_engine` package. The output directory must not already exist. Use a trusted exact checkout, ordinary Python 3.10+ on Linux, an available `/dev/full` device and a writable parent directory. The qualified runs used Python 3.12.14; no third-party dependencies or provider setup are required.

The helper fences the supplied Python module files before and after execution. It does not itself authenticate an arbitrary checkout against Git. The original-source pin record and paired packet contain the exact qualified closure; use those source boundaries when reproducing the recorded result.

A bounded original invocation from a checkout containing the receiving files is:

```sh
READONLY_ORIGINAL_SOURCE=/absolute/path/to/original-ad99-source
READONLY_ORIGINAL_OUT=/absolute/path/to/new-original-controls

timeout --signal=TERM --kill-after=5s 60s \
  python3 -B tools/receiving/readonly-stdout/receive-readonly-stdout-v3.py \
  "$READONLY_ORIGINAL_SOURCE" "$READONLY_ORIGINAL_OUT" original
```

For the recorded original defect, exit 1 and a receipt with 22 accepted checks, four target failures and no harness error are expected. A missing or setup-error receipt is a different result. Do not treat every nonzero exit as the expected reproduction.

Then receive the exact repaired source using the preserved original-control directory:

```sh
READONLY_CANDIDATE_SOURCE=/absolute/path/to/received-ac975099-source
READONLY_CANDIDATE_OUT=/absolute/path/to/new-candidate-controls

timeout --signal=TERM --kill-after=5s 60s \
  python3 -B tools/receiving/readonly-stdout/receive-readonly-stdout-v3.py \
  "$READONLY_CANDIDATE_SOURCE" "$READONLY_CANDIDATE_OUT" candidate \
  "$READONLY_ORIGINAL_OUT"
```

The paired artifact already contains the complete original controls under `independent/original-v3/`. Those exact controls can be used as the last argument without another original run. Candidate mode copies the original SQLite, plan and routing inputs into its new output directory and compares normal stdout bytes with the original raw results. It accepts an original receipt with the expected product failures, provided the original setup had no harness error.

A successful candidate writes `RECEIVING.json`, reports 26 accepted checks with no failures or harness error, and exits zero. Inspect the actual receipt; an outer supervisor's exit is not proof of receiving or cleanup.

## What the course exercises

For each command, the receiver executes a healthy call, a call whose descriptor 1 is physically closed in child pre-exec, a call writing to actual `/dev/full`, and another healthy call. It does not patch `sys.stdout`, mock a writer or wrap the product module in an audit shim.

Preview, inspect and projects also exercise their supported file-output option while stdout is absent. Their newly written file bytes must match the healthy stdout report. History had no file-output option in this exact baseline and is not given an invented one.

Four additional input-refusal controls close stdout while using a missing input or unknown project. Those refusals must still precede output handling and retain their existing error codes. Each invocation checks that retained SQLite data and sidecars, plan and routing inputs retain their bytes and metadata.

The completed project state is fictional local fixture data. No dispatcher, adapter, external worker, provider or installed estate service is invoked. Input/source preservation and process-group observations are the stated evidence; they are not an operating-system-wide I/O audit.

Each owned CLI gets an eight-second wait and bounded TERM/KILL handling if required. Forced signals fail the course. The outer GNU timeout is additional supervision. After interruption, inspect any receipt and the recorded owned processes; nested child groups must not be assumed gone merely because the outer command stopped. Output-directory creation and initial source/expectation reads precede the main receipt guard, so an early setup failure may leave no receipt.

## Preserved receiver corrections

Eight historical files in `archive/` retain the original-first source and correction chronology:

1. Receiver v1 was frozen but never executed. Its history expectation used state names `dispatching` and `running`; a primary-source check corrected those to recorded event names `dispatch_started` and `dispatch_accepted` before execution or candidate intake.
2. Receiver v2 then reached original fixture setup and was rejected because its fictional project identifier contained Unicode outside the original Plan identifier contract. No CLI child ran. The full setup-error receipt is in the packet; it is not evidence of a product stdout failure.
3. Receiver v3 changes only the adjacent expectation filename. The new expectations use ASCII project identifier `receiver-output` and retain Unicode instruction text. This corrected pair was frozen before candidate intake, ran the complete original course, and then ran unchanged against the candidate.

The archive contains the unexecuted v1 and setup-failing v2 source, original expectations, three freeze/correction records, complete original-source pins and primary public contract. It does not rewrite those historical sources to look like the final receiver.

The author maintained-test course is separate. Its final three methods passed. Earlier source staging was interrupted by ENOSPC, and early maintained-test drafts made incorrect assumptions about report identity fields. The complete author record retains those drafts, errors, original reproductions and final source/result. Those three methods are not aggregated into the independent 26 checks.

## Immutable paired artifact

The [paired source and receiving packet](https://drive.google.com/file/d/16Ch54TzfGsDtcJMOjJ7vu1zOHDaB9jFG/view?usp=drivesdk) is **106,482 bytes**, SHA256 `58e432ced7202fe52c44155539469f0d2e0bf4feb5d051a7ee5c0f3815cc5957`. Its raw download, CRC and all 57 payload hashes were verified.

It includes the original ten-module closure, candidate twelve-file source/test/guide set, every receiver/expectation/freeze, raw original and candidate receipts, fictional input databases, full author record, source review and an independently byte-verified primary remote binding for the four published paths. Large raw receipts remain in that packet.

The complete original receipt is 75,889 bytes, SHA256 `95b6fb6cd2da61574eb1a9fdb24e8b39cb3b3607a705b03de28baba492d9ca3c`. The candidate receipt is 70,708 bytes, SHA256 `4523d6e3ed12761424b06b9e33f58e3e4699c969df0c1c7f4cbb5ece1774b08a`.

A first ZIP write failed under shared ENOSPC and left a zero-byte archive. Its metadata is retained. The successful archive was built in memory and saved after exact-size allocation; no source change or receiving replay followed that delivery failure. Subsequent publication/context companions can bind this immutable packet without changing its original-first and draft-at-freeze boundaries.
