# Receive literal task-ID admission from an exact source commit

This utility runs the two frozen local-adapter observers used to review task-ID acknowledgement admission. It stages six source modules from an existing authorized Git checkout, verifies an explicitly selected immutable commit, and produces a receipt that accepts only the complete eight-case contract.

The existing repair owner is [PR 47](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/47). Its [candidate-specific review](https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/47#issuecomment-6135091175) records the remaining truthiness defect at the inspected head. These files provide a repeatable receiver for that owner and subsequent reviewed pins. They do not change production source or supply a second repair.

## What the gate checks

The four strip cases use an actual retained SQLite database and a read-only reopen. Literal blank IDs must produce outcome_unknown with a null retained task ID. A valid Unicode ID containing leading and trailing spaces must be accepted with its exact text intact. Overriding a string subclass's strip() must not change either result. An independent part must still start, and a dependent part must stay blocked.

The four truthiness cases pair string subclasses with native-string adapter controls. A valid literal ID must remain valid when a subclass returns false or raises from __bool__. Neither hook may run, dispatch may not abort, both independent submissions must occur, and the dependent part must remain queued. The native controls use str.__str__ inside the local adapter; they are controls, not a production overlay.

The observers intentionally exit zero when an observation finishes, even if it exposes a defect. receive_task_id_fix.py evaluates the recorded results and returns nonzero when any admission or preservation check fails. The outer receipt.json must contain accepted: true with the explicitly selected source identity for a passing bounded receiving result.

## Run from an existing reviewed checkout

Use Python 3.10 or newer, its standard library, and an already installed Git executable. Select the reviewed source commit yourself and ensure its objects exist in the authorized checkout. The stager reads Git objects; it does not fetch, clone, install, change a branch, or read working source bytes.

Set these absolute paths for your location. The output must be new. Replace the example PR 47 pin with the exact corrected owner pin when one has been reviewed.

~~~sh
fanout_checkout='/absolute/path/to/multi-agent-fanout-engine'
fanout_receiving_tools='/absolute/path/to/docs/receiving/task-id-literal-content-3163ad952d45'
fanout_selected_commit='d3aed88cc89fd91e6c8f28755f003bf72f14e6aa'
fanout_receiving_output='/absolute/path/to/new-task-id-receiving'

python3 -B "$fanout_receiving_tools/stage_source.py" \
  --checkout "$fanout_checkout" \
  --commit "$fanout_selected_commit" \
  --output "$fanout_receiving_output/selected-source"

python3 -B "$fanout_receiving_tools/receive_task_id_fix.py" \
  --source "$fanout_receiving_output/selected-source" \
  --expected-commit "$fanout_selected_commit" \
  --output "$fanout_receiving_output/result"
~~~

The inspected d3aed88 example is expected to fail the truthiness contract. No corrected-owner positive receiving result is claimed here. Earlier source pins and results are preserved in QUALIFICATION.json. A different selected commit requires its own receiving result.

Keep all four Python files together. The gate verifies both frozen observer hashes, disables bytecode writing, and removes inherited PYTHONOPTIMIZE from its child environment.

## Source and output contract

stage_source.py requires a full lowercase 40-character Git commit identity. It recomputes the raw commit, root tree, package tree, and selected blob identities with replacement objects disabled. The six modules are __init__, dispatch, inspection, ledger, plan, and routing. SOURCE.json records every leaf's byte count, SHA-256, Git blob identity and mode.

The AST check covers relative intra-package imports for this explicitly reviewed six-module closure. It is not a general Python dependency resolver. The observers also verify that expected imported modules resolve inside the selected source directory. Use only a reviewed pin whose dependencies fit this receiving scope.

All object reads finish before creating the output. Existing output is refused, and SOURCE.json is written last. Retain incomplete output for inspection; choose a new output for a deliberate retry after understanding the earlier operation.

The result directory contains:

- receipt.json: source and observer identities, platform versions, command records, source preservation and all acceptance checks.
- strip/receipt.json and strip/retained.sqlite3: strip observations with retained state and events.
- truthiness.json: hooks, exceptions, reports, state, events and paired-control observations.
- strip.stdout, strip.stderr, truthiness.stdout and truthiness.stderr: captured child outputs.

Each observer has a 60-second deadline. A nonzero child exit or timeout stops the gate. Partial stdout and stderr remain available, and failed-operation.json records the command, exit status and timeout. Timeout is represented by a null exit code and timed_out: true. If the first observer fails, the second is not started. An incomplete course has no success receipt.

The receiving result applies to these eight local-adapter cases, the selected source and the recorded Python/SQLite platform. It does not establish estate service binding, provider operation, application installation or unrelated functionality at the same commit.

## Utility verification and preserved evidence

QUALIFICATION.json records the exact historical pins and evidence hashes. Frozen observer scope strings retain their original review context and PR 25 attribution; the outer manifest and receipt identify the source selected for a new course.

The stager was exercised on actual commit 0317b4bc80638a8e952857aa5966b0e20d1fab72 in a checkout whose working dispatch.py differed. All six staged leaves matched the previously received original capsule. Existing output and an abbreviated ref were refused without changing source or prior output.

The receiver's timeout delta was checked with controlled TimeoutExpired injection. Partial binary stdout/stderr were preserved, a failure record was written, the command returned nonzero, and no second observer started. That check executed no adapter workload. Both utilities received independent source review; the behavioral observers remain byte-for-byte frozen. Compact verification records are in proof/.
