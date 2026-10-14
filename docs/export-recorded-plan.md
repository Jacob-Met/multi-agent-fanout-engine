# Export a recorded native plan

Use this command when a project exists in a ledger and you need its authored plan as a JSON file for reading, editing a separate proposal, or passing to the existing plan consumers. It reads one selected project and verifies its stored native plan and digest.

From this source checkout, or an environment containing this revision:

```sh
python -m fanout_engine.projects --database retained.sqlite3
python -m fanout_engine.export_plan \
  --database retained.sqlite3 --project example \
  --output recorded-plan.json
```

The first command can help find the exact project identifier. The second creates a new file; choose a path that does not already exist. Without `--output`, the command writes the complete JSON document and one newline to stdout.

## Document and identity

The output has the native plan shape `{"project": ..., "parts": [...]}`. It uses canonical sorted-key UTF-8 JSON and one final newline. It preserves authored part order, dependency order, exact instruction strings, tag order and repeated tags accepted by direct native construction. It validates the retained project identity and plan digest before producing output.

The command does not export part states, worker or task identifiers, routes, artifacts, evidence or event history. Those remain available through `inspect` and `history`. Missing or malformed runtime rows do not invalidate an otherwise valid authored plan here. The existing native snapshot query still requires its schema columns to be readable. No schema is initialized, repaired or migrated.

This is a plan export, not a database backup or a restore operation. It does not record the exported plan, dispatch work, change saved work, or authorize reusing an execution key. An invalid or missing selected plan is refused; an unrelated project's malformed header is outside the selected export.

## Use the existing comparison and preview tools

Keep the exported file as the original. Edit a separate copy using your normal editor, then compare the two authored documents:

```sh
python -m fanout_engine.compare \
  --before recorded-plan.json --after proposed-plan.json \
  --output comparison.json
```

To inspect routing with an explicit existing routing configuration:

```sh
python -m fanout_engine.preview \
  --plan recorded-plan.json --routes routes.json \
  --output preview.json
```

These consumers retain their own size limits and parsing rules. In particular, their current JSON parser sorts and deduplicates tags. A native plan constructed directly with repeated or differently ordered tags is exported exactly, but may receive a different digest when those consumers parse it. The export command does not change that behavior or claim that arbitrary native constructor identities survive every downstream parser. Ordinary parser-compatible plans can be exported and consumed without this normalization difference.

Comparison and preview describe authored plans; they do not adopt the proposed plan into a retained ledger. Use the existing consumer guides for their full input and output contracts.

## Read-only and output behavior

`--database` is a literal filesystem path, including names containing characters that resemble a SQLite URI. The command uses the existing read-only opener and SQLite snapshot query. It does not create a missing database or missing parent directory and does not initialize an empty file.

The complete plan is read and validated before output publication. File output first applies the existing inspector's database/output path guard, which refuses reserved SQLite `-wal`, `-shm` and `-journal` destinations even when those files do not yet exist. It then uses the existing exclusive publication helper: an occupied path, including the input database itself, is refused and retained. The command does not create a missing output parent. SQLite's ordinary locking and WAL visibility apply; this is not an authenticated or immutable view of arbitrary out-of-band database edits.

Exit statuses are:

| Status | Meaning |
| --- | --- |
| 0 | The complete plan was written to stdout or a new file. |
| 2 | Arguments, database reading or selected native-plan validation were refused. |
| 1 | Output publication failed after the plan was read. |

An output stream failure can leave a partial stream. It does not perform a ledger transition. Existing file output is never intentionally overwritten.

## Python API

```python
from fanout_engine.export_plan import export_plan
from fanout_engine.ledger import Ledger

with Ledger.open_readonly("retained.sqlite3") as ledger:
    document = export_plan(ledger, "example")
```

The returned dictionary and its nested lists are detached from the retained data. The API uses the supplied ledger's existing transaction context and does not commit or roll back the caller's transaction. It raises the existing `InspectionError` for a missing or invalid selected native plan.

## Focused qualification

```sh
python -B -m unittest discover -s tests -p test_export_plan_b3d7b32e.py -v
python -O -B -m unittest discover -s tests -p test_export_plan_b3d7b32e.py -v
```

The tests create private fictional ledgers and exercise exact native export and detachment, caller transaction ownership, malformed headers, selected-project scope, deliberately incomplete runtime rows, literal paths, real CLI output, exclusive files, reserved SQLite sidecars and refusals. The saved ordinary plan also feeds the unchanged comparison CLI. On POSIX, real closed stdout and a full output device exercise output failure without mutating the database. They do not operate an external worker or an estate ledger.
