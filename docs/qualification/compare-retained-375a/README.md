# Retained-plan comparison receiving

This qualification accompanies `fanout_engine.compare_retained`: a caller can
compare a revised plan with a validated saved project before creating a new
project or asking an operator to reconcile an existing one. The command reads
the ledger through the existing read-only inspection surface. It makes no Hub
or provider call.

## Source and review

The independently reviewed adapter has SHA-256
`8d3b64e2b4efd61bca56a9f7dbc482f1794866de45bb9527f679a384555bf17e`.
Consumer reviewed this exact source in normal and optimized Python against the
published comparison increment `2677396c6c12357237704658b814483d8eb8d96e`.
The head then received the current repository source at
`77217a07a76e8ee6554ffe11808b1bdcbaf680ee`, tree
`a2e9d90f2491dd42706309f798b84d00603c0ec4`, with the adapter, its nine test methods,
and its usage guide unchanged. All 150 maintained tests passed in normal and
optimized Python 3.12.14 on that composition.

The independent driver here is Consumer's review with only the source-root
selection made portable. The head reran its five courses in both modes on that
current-source composition. The original peer receipts and full run logs are
retained separately from this concise source qualification.

## Repeat the native receiving courses

From the repository root:

```bash
python -B -m unittest discover -s tests -v
python -B -O -m unittest discover -s tests -v
python -B docs/qualification/compare-retained-375a/independent_review.py
python -B -O docs/qualification/compare-retained-375a/independent_review.py
```

The driver also accepts an explicit repository root as its first argument. It
checks the frozen adapter hash before running. It creates disposable SQLite
fixtures and exercises the actual command from an unrelated working directory
with spaces and literal URI punctuation in the input paths.

Its courses cover the saved-plan admission conflict followed by comparison;
exact direct-Part tags, ordering, digest and keys; running, completed and failed
states; committed WAL state while another connection holds an uncommitted
write; a malformed later evidence field; distinct missing-project status; and
candidate duplicate-key and FIFO refusal. It verifies input bytes, the saved
event history and the external writer are preserved. A complete JSON result
appears only after the comparison has passed validation and serialization.

The focused unit suite additionally covers identical native plans, explicit new
project identity, the input and part-count bounds, and output-device failure.
These are native isolated SQLite and command-line checks. They do not establish
an installed estate workflow or any provider execution outcome.

See [the usage guide](../../compare-retained-plan.md) for the API, command,
report fields and exit statuses.
