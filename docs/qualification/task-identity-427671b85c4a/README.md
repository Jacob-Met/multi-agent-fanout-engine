# Accepted task identity qualification

Reviewed source: [a5959edc361b4345ec6c356e8e40a294b1e6b3d6](https://github.com/Jacob-Met/multi-agent-fanout-engine/commit/a5959edc361b4345ec6c356e8e40a294b1e6b3d6), tree `6b6ac5d71602fece8de8659b401a2cf00a7d24a9`, parent `484ad9270b6c5e49db87171eb26ac516d592ddd6`.

The ledger now validates literal nonblank UTF-8 task identifiers before SQL and
retains their exact plain-string characters in both the part row and acceptance
event. The source change is seven lines replacing the two-line `mark_running`
guard, accompanied by five regression methods and [the task identity guide](../../task-identity.md).

## Evidence

- [Author qualification and independent source review](qualification.json): native
  CPython 3.14.4 / SQLite 3.46.1 on Linux. All 207 tests pass on the current-parent
  composition. Five focused tests also pass under actual optimized Python; their
  CLI subprocesses inherit that mode. The demo and whitespace check pass.
- [Independent native receipt](independent/native-receiving.json): a separately
  authored sixteen-check SQLite course passes 16/16 on the exact candidate and
  3/16 on the parent. It checks invalid admission, exact literal retention,
  SQLite adaptation, equality and truthiness overrides, idempotence, reopening,
  dependency blocking and one local adapter call across repeated dispatch.
- [Independent CLI receipt](independent/cli-receiving.json): the actual inspect
  and history commands both return exit 0 with empty stderr. Their parsed reports
  preserve `  task/Ω#1  ` exactly; the retained SQLite bytes stay unchanged.
- [Independent course](independent/independent_course.py) and
  [original execution runner](independent/run_receiving.py) are retained unchanged.
  The runner records the original isolated paths. The course accepts explicit
  paths and can be reused from another checkout.

The original three-file freeze was independently reviewed before publication.
After current main advanced, the source reviewer confirmed that replacing only
the new guard with the old guard restores every byte of the current-main ledger.
Complete Git tree comparison preserves all 207 unrelated parent leaves and modes.

The initial native author baseline contains existing SQLite ResourceWarnings.
Its 193-test count and the initial 198-test candidate count refer to the earlier
pinned parent; the 207-test result belongs to the final source above. The raw
independent receipts retain their original timestamps and paths. No test result
is claimed for later main changes.

## Repeat the independent candidate course

From the repository root, choose a new output directory:

```sh
mkdir task-identity-receiving
python -B docs/qualification/task-identity-427671b85c4a/independent/independent_course.py \
  --source . \
  --database task-identity-receiving/ledger.sqlite3 \
  --result task-identity-receiving/result.json
```

Read the resulting JSON and require `passed == total == 16` with an empty
`failed_names` list. The course deliberately records semantic failures in JSON
while still exiting normally, which permits the parent comparison; process exit
alone is not a pass. Use a fresh directory for another run.

The course creates only local fixture work and SQLite evidence. This qualification
does not install a worker, contact a provider, execute hosted Actions or promote
the source to main.
