# Queued-route receiving evidence

This directory preserves the independent receiving sources for the advisory queued-route CLI and its later interaction with queued withdrawal. Product source is tracked in [PR77](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/77). These files add receiving evidence; they do not change the ledger, router, dispatcher, inspection logic or adapters.

## Qualified outcomes

| Course | Exact boundary | Recorded result |
|---|---|---|
| Original controls | Original `9fe49691944cacf666e1c37f526c0d26fc1a4ee1` source | 9/9 controls; the new CLI was absent, an expected capability gap |
| First CLI candidate | `queued_routes.py` SHA256 `68cdff46107e537abbf348f9aad38494b66f37b50d2b938babb743e126de1386` | 41 accepted checks and one clean-diagnostic failure across 35 actual CLI children |
| Accepted CLI successor | `queued_routes.py` SHA256 `7515cdd5e49903a8a279eed8f093e265d54e707b0712e17230554135f085f17d`, original inherited runtime | 42/42 using the unchanged frozen oracle and 35 actual CLI children |
| Later withdrawal interaction | Received head `082c07a0ef0f2cfd9f842179ea677463b2837931`, tree `78bed873de325736d990867524859c670817e054` | 11/11 on ordinary-user ThinkPad fixtures, with two direct CLI children and one actual withdrawal API call |

The first candidate already returned the specified failure exit code when standard output was absent. It emitted an AttributeError traceback because Python exposed `sys.stdout` as `None`. The independently frozen clean-diagnostic criterion failed. The successor adds a narrow guard inside the existing output-error path. A separate source review also corrected a maintained-test SQLite connection that a connection context manager did not close.

Author verification remains separate: eight maintained methods passed before that finding, and three affected methods passed after the repair. These are separate author courses, not a full rerun of all nine successor methods. A separate direct two-case output witness is retained in the first packet and is not added to the 42 checks.

## Run the narrow withdrawal interaction

The reusable exact pair is:

- `tools/receiving/queued-routes/receive-withdrawal-preview-v1.py`
- `tools/receiving/queued-routes/withdrawal-preview-expectations-v1.json`

Keep the expectations file beside the helper. It accepts the exact source root and a **new, nonexistent** owned output directory. Use trusted source, a writable parent directory and a POSIX Python environment with process-group support. Python 3.10+ is the source prerequisite; this particular course ran with ordinary Python 3.14.4 on Linux, as user `jacob`, UID 1000. The prior cloud courses used Python 3.12.14. No third-party package installation is required.

The qualified source is the exact received head above, which composes the accepted CLI with canonical ledger base `5e23792109a8bfbd60427e35098adf4523014f63`. It includes thirteen Python modules. The helper explicitly admits these two key module hashes:

| Module | SHA256 |
|---|---|
| `fanout_engine/queued_routes.py` | `7515cdd5e49903a8a279eed8f093e265d54e707b0712e17230554135f085f17d` |
| `fanout_engine/ledger.py` | `7a1611b2904515432be42aa84005e4d6ec31268b6b365c722df17748e26aa2f0` |

The native packet's admission record pins all thirteen transferred modules. The helper also fences every Python module in the supplied package before and after execution. That preservation check does not independently authenticate an arbitrary checkout. Use the exact received source when reproducing this recorded qualification; a later main branch is a different source boundary.

From a checkout containing the receiving files, a bounded GNU/Linux invocation is:

```sh
RECEIVING_SOURCE=/absolute/path/to/exact-received-source
RECEIVING_OUT=/absolute/path/to/new-owned-output

timeout --signal=TERM --kill-after=5s 45s \
  python3 -B tools/receiving/queued-routes/receive-withdrawal-preview-v1.py \
  "$RECEIVING_SOURCE" "$RECEIVING_OUT"
```

The helper creates only its synthetic project, routing input and SQLite database beneath the new output directory. It records a queued root, dependent child, unrelated queued part and retained unknown/running controls. The first real CLI call must select the root and unrelated part. An actual `Ledger.withdraw_queued` call then records the root as failed with one `queued_withdrawn` event. After closing and reopening the database, the second real CLI call must exclude that root, keep its child blocked and still select the unrelated part.

Both CLI calls must preserve database bytes, sidecars, metadata and SQL rows. The withdrawal is the sole intentional state change. The root's stored identity and null submission references remain intact, as do the unknown/running controls. The helper calls no dispatcher, adapter, Hub, provider or installed service.

A successful run writes `RECEIVING.json` and exits zero. Each CLI child has an eight-second wait followed by bounded TERM/KILL handling for its own process group; forced termination fails the course. The outer timeout is additional supervision, not proof of cleanup. After interruption, inspect any receipt and the recorded owned processes. Output-directory creation and initial source/expectation reads occur before the main receipt guard, so an early setup failure may leave no receipt. Ordinary trusted Python execution was used; the separately archived native transfer wrapper uses assertions and was not run under optimization.

## Historical original-first sources

The `archive/` directory keeps eleven files byte-exact:

- Original control helper, adjacent expectations, original freeze and complete original-source pins.
- Full route-preview helper, adjacent observer and expectations, primary public contract, and candidate-oracle freeze.
- Later interaction freeze and the exact canonical queued-withdrawal contract read before its execution.

The original controls and complete candidate oracle were frozen before candidate intake. Their [public contract](https://github.com/Jacob-Met/hamon/issues/143#issuecomment-6142035765) describes whole-configuration route validation and read-only advisory output; it does not change dispatch admission timing.

The full candidate helper is historical. Its expectations name the fixed original-source path:

```text
/dev/shm/hamon-worker-two-queued-routes-3795/original-9fe49691
```

It also expects a prior original-control directory containing the synthetic retained database and route input. Preserve that recorded setup when reading the evidence. This archive is not presented as a portable one-command runner. Rehosting or changing the fixed path would create a new helper/qualification boundary. The recorded helper and observer remain unchanged.

That full course used an audit/runpy observer to run the actual unmodified CLI module and record selected Python open, SQLite connect, socket connect and process-spawn events. It was not an operating-system-wide filesystem or network audit. The separate direct output witness and later native interaction used ordinary `python -B -m` CLI subprocesses without that observer.

## Immutable delivery and failure chronology

The [original/v1/v2 paired packet](https://drive.google.com/file/d/1c-nxcXMteRKJU7G3CHneKtZn7SMvGWXE/view?usp=drivesdk) is **247,050 bytes**, SHA256 `32cb70849280ebc5cf8000fc14800460231d5005c77176e76722996d30c5b9d2`. Its raw download, CRC and all 185 payload hashes were verified independently. It contains original source, candidate source, oracle freezes, raw receipts, process/audit observations, author results and both source reviews.

That packet preserves an initial original-control setup failure from ENOSPC, the unchanged successful original retry, the first candidate's diagnostic finding, the accepted successor, a capacity-floor stop before the successor receiver launch, and the separately completed direct output witness. Incomplete or unstarted attempts contribute no passing count.

The [current native integration packet](https://drive.google.com/file/d/1zua5psXq8HqRPiPn4WNV1KWT5L_gCraz/view?usp=drivesdk) is **53,296 bytes**, SHA256 `ac0e8303f538b42fa9a9486a8cf73715448bf47e1ac054fe71332e2f959cf8a5`. Its raw download, CRC and all 31 payload hashes were also verified independently. It contains the exact current thirteen-module closure, helper/expectations, raw 11-check receipt, synthetic database, native admission, process custody and source review. Its raw receipt is 33,441 bytes, SHA256 `c928663b200632d35a055f914ea084f9e325a821f81d6cca8ed04cc0fb5a0046`.

A separate local ENOSPC occurred while writing the current integration's admission record, before any local receiver started; that zero-byte file is retained. The subsequent ordinary-user native fixture was freshly identified through the supported device tools. Its receiver and both CLI children exited naturally, with empty stderr and absent owned process groups. A preupload guide-only correction attributes assertion use to the native transfer wrapper; no helper, source or runtime result changed.

The native course is explicitly a **post-intake integration** of the accepted CLI and newer canonical ledger. It neither repeats nor extends the prior 42-case count. Canonical `review.py` was transferred and fenced but not independently exercised. These artifacts establish the recorded source-consuming workflows; they make no installed estate parity, live worker availability, provider-result or full current-tree suite claim. Later source publication bindings remain separate so neither immutable packet needs rewriting.

## Final product publication binding

PR77 merged as `ad99d83d23e029cc383b2adf8a999f23be642f8c`, tree `4cd5e997f9d8ac7c68d03ab5ea818667b8d0a20a`, with head `c742a0dc188b255ef052569b87164fac7442f9bf` and main parent `185547f7bcff5e9bcc4527af49148c6fbf19120f`. The [separate final publication companion](https://drive.google.com/file/d/1HDDyJk4VjN6eaEJpT3wyc9VVlizWjTDE/view) is 4,150 bytes, SHA256 `fd3a391cba3bec1c35ba5fa1084aea0fde55410d75535a54bc425d3744d573e3`.

The imported runtime modules remain exact to the received 5e composition. Later comparison and evidence additions were reviewed as source preservation and were not rerun as part of the native interaction course. The final source binding preserves the earlier packet boundaries and their exact counts; neither archive was rewritten.
