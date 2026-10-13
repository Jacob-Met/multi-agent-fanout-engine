# Discover retained project identities

When you have an existing ledger but do not know the exact project ID, list the
stored plans first:

```sh
python -m fanout_engine.catalog --database work/dispatch.sqlite3
```

The command requires Python 3.10+ and this package. It opens only an existing
regular file using the same read-only connection as the project inspector.
It performs no schema initialization, recovery transition or task submission.

## Report

The complete report is canonical UTF-8 JSON followed by one newline:

```json
{"projects":[{"declared_part_count":7,"plan_digest":"<native SHA-256 digest>","project_id":"sample"}],"schema_version":1}
```

Projects are sorted by their exact validated ASCII identifiers. Case is
significant: `Alpha` and `alpha` are distinct project IDs. No normalization,
filename or observation time is added.

| Field | Meaning |
| --- | --- |
| `schema_version` | Version 1 of this catalog document. |
| `projects` | One row for each valid stored project header. |
| `project_id` | Exact identifier to pass to `fanout_engine.inspect --project`. |
| `plan_digest` | Native digest verified against the complete stored plan. |
| `declared_part_count` | Number of parts declared in that verified plan. |

The reader captures all raw headers with one SQL statement, then validates every
stored plan and its identity using the existing inspector's rules. Direct native
tag repetitions and dependency order keep their effect on plan identity. A
malformed plan, mismatched digest, or repeated project ID refuses the entire
catalog before any success output. No partial catalog is returned.

An empty header collection produces `projects: []`. It does not certify the rest
of the database schema. The catalog reads plan headers only: declared counts do
not confirm retained part rows, task states, evidence, or dispatch readiness.
For example, a header may be valid even when a part row is missing. Inspect the
selected project to validate its retained parts and observe their actual states:

```sh
python -m fanout_engine.inspect --database work/dispatch.sqlite3 --project sample
```

Each invocation has its own read snapshot. A later inspection can observe a
newer committed state. The catalog does not reserve work or verify external
effects. SQLite's normal read-only locking and WAL bookkeeping still apply, as
described in [the retained-ledger guide](inspect-ledger.md).

## Save a catalog

```sh
python -m fanout_engine.catalog --database work/dispatch.sqlite3 --output new-catalog.json
```

File delivery uses the inspector's existing protected new-file writer. The
destination must be absent and its parent must exist. Existing entries and the
selected database's reserved SQLite sidecar paths are refused; publication never
falls back to replacing a file. A successful export prints no status text to
stdout. See [the complete output contract](inspect-ledger.md)
for aliases, cleanup failures and stable-path requirements.

| Status | Meaning |
| --- | --- |
| `0` | The complete catalog was written and flushed or published as a new file. |
| `1` | Output was refused or failed. A post-publication cleanup failure reports that publication completed before cleanup failed. |
| `2` | Invalid options, unreadable/incompatible input, or inconsistent stored headers. No catalog is written. |

Diagnostics go to stderr. Missing files and incompatible tables are not created
or repaired. Normal process termination remains outside these controlled
statuses.

## Python use

```python
from fanout_engine import Ledger
from fanout_engine.catalog import catalog_projects

with Ledger.open_readonly("work/dispatch.sqlite3") as ledger:
    report = catalog_projects(ledger)
    for project in report["projects"]:
        print(project["project_id"], project["declared_part_count"])
```

The returned JSON-compatible values are detached. `Ledger.project_headers()` is
the lower-level single-statement reader; it returns unvalidated raw header rows.
Neither reader commits a caller's existing transaction or changes ledger rows.
