# Save an advisory queued-route report with the ThinkPad reader

This dated adoption adds the maintained `queued-routes --output NEW.json` capability to the existing `hamon-fanout-read` command. It uses a new private installation of all 20 modules from one published source tree. Staging leaves the working command unchanged; activation is a separate guarded step.

The report describes route choices for recorded queued-ready parts. It does not submit work, reserve a worker, change a route, dispatch, retry or reconcile anything. Use an explicitly selected local ledger and routing file.

## Operator command after qualified activation

From the already admitted authored nine-event handoff sample:

```sh
hamon-fanout-read queued-routes \
  --database /home/jacob/hamon-e1438c9d058f-fanout-reader-closure/candidate-course/current-start-run/retained.sqlite3 \
  --project fixture-handoff-51df5b72e832 \
  --routes /home/jacob/hamon-e1438c9d058f-installed-queued-output/inputs/routes.json \
  --output /home/jacob/hamon-e1438c9d058f-installed-queued-output/operator-queued-new.json
```

The final path must be new and its parent must already exist. Omit `--output` to keep the unchanged JSON-to-stdout behavior. The retained sample has `summary` dependency-ready and `handoff` blocked; `audit` remains outcome-unknown. A route in this report is advisory and does not authorize replay of the audit.

Successful file output returns 0 with empty stdout/stderr. Input or routing admission errors return 2; a missing project returns 3. Output failures return 1 after a valid report has been formed. Existing destinations and protected database/sidecar aliases are refused. The maintained publisher can report a cleanup error after publication; a nonzero exit alone does not prove the output is absent. Inspect the named file and diagnostic before selecting any next action. No parent creation or replacement of an occupied output is promised.

These commands use the previously produced fictional sample. No account data, new ledger workflow or adapter execution is part of this adoption.

## Exact source and installation boundary

Repository: [multi-agent-fanout-engine](https://github.com/Jacob-Met/multi-agent-fanout-engine).

- Maintained commit: `93c19c7fc74bda6652ab00a3d03266f53cbe5c1c`.
- Complete source tree: `5d0f044ada289195eb427a0a7ba902adb977d61b`.
- [source-manifest.json](source-manifest.json) lists every one of the 20 module byte lengths, SHA256 values, Git blobs and source modes.
- New private version: `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-93c19c7fc74b-queued-output-v1`.
- Existing alias: `/home/jacob/.local/bin/hamon-fanout-read`.
- Preserved previous target: `/home/jacob/.local/share/hamon-tools/hamon-fanout-read-36f83e0767cf-queued-routes-v1/hamon-fanout-read`.
- Canonical runtime: `/usr/bin/python3.14`, CPython 3.14.4, SHA256 `52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41`, host `hamon-thinkpad`, account `jacob` UID/GID 1000.

This is a complete source installation made with `venv --without-pip`, not a wheel installation. It does not contact a package registry, install dependencies or use system site-packages. The wrapper invokes its fixed private interpreter with `-I -B`. The actual interpreter symlink and its canonical referent are recorded separately. All seven literal routes remain: projects, inspect, history, review, blockers, compare-inspections and queued-routes. Dispatch remains outside the wrapper.

Seventeen modules are byte-identical to the qualified installed `36f83e0767cf` source. The three maintained changes are:

| Module | Maintained change and prior qualification |
| --- | --- |
| `queued_routes.py` | [PR110](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/110): optional exclusive report file, default bytes/status preserved. |
| `plan.py` | [PR109](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/109), from PR37: converts an unencodable canonical plan to the existing PlanError boundary. |
| `review.py` | [PR107](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/107), from PR92: visibly escapes twelve bidi controls in the saved project-review page. |

The installed-output course exercises queued JSON/file output and the unchanged comparison HTML path. It carries the complete maintained plan/review bytes with their prior qualification; it does not claim to re-execute the malformed-Unicode or bidi-specific cases. This distinction avoids mixing old and new modules while keeping the native result scope precise.

## Source checkpoint and authentic inputs

Before this candidate existed, the working installed reader made one inherited-PATH request with `--output`. Its actual result was a clean parser status 2, empty stdout, a 322-byte module-style usage diagnostic and no output. The original receiver recorded CHARACTERIZED 8/8, with 97 protected entries, 13 inputs and seven complete roots unchanged. PID 1061074 was reaped; outer PID 1061007 and the child were absent at postexit. This is evidence of the original missing capability.

The completed original record is in the owned namespace `/home/jacob/hamon-e1438c9d058f-installed-queued-output`. Its raw receipt SHA256 is `2d5d69be8d75a105ba98c405ee9ce2f89847ca39480b6d68455b87501bb5008d`.

The received queued oracle is the complete 1,010-byte JSON including its final LF, SHA256 `6364d6844f178fc8bf3e2e398abfa093a025082a741d53d7d44c99cba5d7133d`. Routing input is 267 bytes, SHA256 `d421f5e5886d1a1fea9c50b862d311e882a66b23fb11c1ec5e359f926349ee22`.

The saved comparison uses the already received genuine same-run Windows180 pair from PR101: 3,437-byte first inspection and 4,414-byte second inspection. Its complete native JSON is 12,420 bytes, SHA256 `9d403925e7a6544e7f799fc05608383a339d34d11441c725119ac05575cbdb45`. The 48,222-byte HTML oracle has SHA256 `2eb35e0bd3c2a08e7472d24334425dec6e4f9468e11b9a2ab1e5e48a2b3abdf3`. This HTML has already been rendered and received in a browser; exact byte identity permits reuse of that result without another browser course.

## Separate stages and status

At this immutable source checkpoint, **stage, activation and withdrawal are UNRUN**. Later source-linked receipts and the operator handoff record observed results without rewriting these source bytes.

The helper is deliberately bound to this device, account, admitted inputs, original characterization and new version name. It is an inspectable adoption recipe, not a general-purpose installer. The four published files alone do not recreate the admitted external ledger or frozen original receipts.

After the receiving controller and configuration are reviewed, the single stage command is:

```sh
/usr/bin/python3.14 -I -B /home/jacob/hamon-e1438c9d058f-installed-queued-output/candidate-source/install_queued_output_reader.py stage
```

Stage has one private-venv setup and exactly four native consumer calls:

1. Default queued output must equal all 1,010 oracle bytes.
2. A new `stage/exported-queued.json` must receive those same bytes with empty streams.
3. Reusing that exact destination must return 1 and preserve its complete identity.
4. Existing comparison HTML must equal all 48,222 oracle bytes, and its sole strict-MIME download must decode to the exact 12,420-byte native JSON.

Setup is bounded by 60 seconds plus a 3-second post-kill collection window. Each product call is bounded by 15 seconds plus 3 seconds. A refusal or timeout is recorded before the helper stops. The helper does not proceed to later observations after failure, infer descendant termination from parent reaping, or silently retry. Outer receiving uses its own separately recorded budget.

Before and after stage, all old versions, input trees, source modules, canonical interpreter, original records, database/sidecars and active alias are compared. The new version receives its own complete byte/mode/mtime/membership snapshot after setup and before native observations. No bytecode or installed module modification is expected.

## Guarded activation and recovery

Activation needs the accepted inactive stage, exact source publication/readback and separate authorization. The helper checks the old alias identity immediately before replacing it with a newly created symlink to the qualified version. It then makes exactly one inherited-PATH queued file export into `installed/queued-routes.json`, checks the entire oracle, and records the actual alias and all preserved state.

```sh
/usr/bin/python3.14 -I -B /home/jacob/hamon-e1438c9d058f-installed-queued-output/candidate-source/install_queued_output_reader.py activate
```

A failed or interrupted activation is not automatically rolled back. Inspect `activation-failed.json`, the actual alias target/inode and the retained version/raw outputs before deciding what happened. An observer failure after a successful switch can leave the new alias active.

The separate `withdraw` phase requires the exact installed receipt and current new alias before restoring the previous target through a fresh symlink. It preserves both versions and gives the restored link a new identity. Withdrawal is **UNRUN** unless separately authorized and received. No source or receipt in this guide claims otherwise.

Existing [queued route documentation](../../queued-routes.md), [installed queued reader](../thinkpad-queued-routes-e1438c9d058f/README.md) and [installed HTML adoption](../thinkpad-comparison-html-e1438c9d058f/README.md) remain separate references. Verify their recorded source and status when following them.
