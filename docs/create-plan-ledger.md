# Create a queued ledger from an authored Plan

Create a **new** SQLite ledger from a saved Plan file without writing Python code:

```bash
python -m fanout_engine.create_ledger --plan plan.json --database work.sqlite3
python -m fanout_engine.inspect --database work.sqlite3 --project local-review
python -m fanout_engine.export_plan --database work.sqlite3 --project local-review --output recorded-plan.json
```

An ordinary input for those commands is:

```json
{
  "project": "local-review",
  "parts": [
    {"id": "draft", "instruction": "Write the local draft.", "tags": ["writing"]},
    {"id": "review", "instruction": "Read the draft.", "depends_on": ["draft"], "tags": ["review"]}
  ]
}
```

The new database contains one recorded project, all parts in `queued`, their native payloads/digests/idempotency keys, and one `plan_recorded` event. Submission, worker, route, artifact and evidence references are absent. A queued part may still depend on another queued part; creation does not run anything or establish completion evidence. You can inspect it, export its Plan, compare a revised Plan, or use the existing explicit queued-withdrawal command.

## Input and native identity

The command reuses the existing comparison file reader and `Plan.from_dict` unchanged. Input must be a regular UTF-8 JSON file of at most 1 MiB with at most 256 parts. Duplicate JSON object keys and nonfinite JSON numbers are rejected. Existing native Plan validation handles identifiers, required fields and dependency graphs.

The existing file parser sorts and deduplicates tags. Part and dependency order remain authored. An exported direct-constructor Plan with repeated or differently ordered tags may therefore acquire a different digest when parsed here. This is the same parser contract used for saved-file comparison and preview, not an exact recreation of every direct Python constructor value.

The receipt distinguishes the SHA-256 of the exact captured input bytes from the digest of the admitted native Plan. Whitespace in the input JSON affects the input hash without changing a parsed Plan. The command does not modify the input. A concurrent external edit is not authenticated; the receipt identifies the bytes this invocation captured.

## Complete new-file publication

The full input is parsed before destination admission. The command records the Plan in its own temporary SQLite file through the unchanged Ledger API, closes that connection, and captures the complete database bytes. Its private preparation is cleaned up before those bytes are published through the existing exclusive new-file publisher.

The destination must be new and its parent must already exist. Existing files, directories, links and racing occupied destinations are refused; the command has no overwrite option. A basename ending in `-wal`, `-shm` or `-journal` is refused, case-insensitively. Any existing corresponding destination sidecar, including a directory or dangling link, also causes refusal. These checks prevent adopting stale sidecar files or selecting a reserved sidecar name for a fresh ledger.

The sidecar check occurs immediately before publication. It is a check of stable filesystem paths, not protection against hostile simultaneous namespace changes. Existing hard-link publication and filesystem support requirements remain unchanged. No output parent is created, and no existing ledger is opened for mutation or migration.

## Receipt and exit status

Successful publication writes one canonical UTF-8 JSON object plus LF to stdout, with exactly these keys:

| Key | Meaning |
| --- | --- |
| `schema_version` | `1` |
| `database` | The literal `str(Path(argument))` filesystem name, without absolute-path conversion or SQLite URI interpretation |
| `project_id` | The admitted native project identifier |
| `plan_digest` | Native canonical Plan digest |
| `part_count` | Number of admitted parts |
| `input_sha256` | Hash of the captured input file bytes |
| `database_sha256` | Hash of the complete closed database bytes published by this invocation |

The receipt is fully encoded before destination publication. SQLite event/update timestamps are new recording timestamps; separate invocations need not produce identical database bytes. The database hash is an identity receipt, not proof of source authenticity.

| Status | Result |
| --- | --- |
| `0` | Complete database publication and confirmation output succeeded. |
| `2` | Arguments, input parsing or private preparation failed before destination publication. |
| `1` | Destination admission, publication or confirmation output did not complete normally. Inspect the destination before retrying. |

An occupied destination, reserved basename or existing sidecar is a destination-admission refusal (status 1). Invalid input takes precedence and returns status 2 even if a destination is occupied or reserved.

Publication errors can occur after the complete destination was linked but before temporary-file cleanup finished. Status 1 therefore does not mean the destination is absent. If stdout is closed or fails after publication, the diagnostic explicitly says **database was published; confirmation output failed**. Do not blindly retry: inspect the existing destination and its project. The command never deletes a published database in response to a later confirmation error.

## Scope and verification

This command creates a fresh queued project from an authored Plan. It does not restore runtime state, events, evidence or prior execution. Reusing a project identifier in a new database does not authorize replaying prior external work. There is no worker selection, dispatch, provider operation, reconciliation or automatic retry.

Existing Plan, Ledger, schema, parser, publication and stdout helpers remain unchanged. The new command uses parsed native values and does not change the separate admission contracts for arbitrary Python objects.

Run the focused maintained checks from the repository root:

```bash
python -B -m unittest discover -s tests -p 'test_create_ledger_b3d7b32e.py' -v
python -O -B -m unittest discover -s tests -p 'test_create_ledger_b3d7b32e.py' -v
```

They exercise actual new-file creation, complete native rows and receipt, existing inspection/export consumers, inherited input limits, output/sidecar preservation, controlled preparation and late-publication failures, and real closed/full stdout where the platform supports those cases. Platform-specific skips remain explicit.
