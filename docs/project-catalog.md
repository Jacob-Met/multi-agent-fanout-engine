# Discover projects in a saved ledger

List the project identifiers stored in an existing fanout ledger before selecting
one for detailed inspection:

~~~sh
python -m fanout_engine.projects --database "work/dispatch.sqlite3"
python -m fanout_engine.inspect --database "work/dispatch.sqlite3" --project sample
python -m fanout_engine.history --database "work/dispatch.sqlite3" --project sample
~~~

The first command requires only the database path. Use a returned project ID
unchanged in the existing inspection or history command.

## Catalog contract

Successful stdout is canonical UTF-8 JSON followed by one newline:

~~~json
{
  "schema_version": 1,
  "project_count": 1,
  "projects": [
    {
      "project_id": "sample",
      "plan_digest": "the recorded native SHA-256 digest",
      "part_count": 7
    }
  ]
}
~~~

The example is formatted for reading; actual output uses compact canonical JSON.
Projects appear in ascending, case-sensitive project-ID order, independent of
insertion order. Every entry contains its exact native ID, plan digest and number
of authored parts. An initialized ledger with no projects produces an empty
array and a zero count.

One SQL statement captures every stored plan header. Each complete plan is then
validated through the existing native inspector's plan/digest validator before
the catalog is returned or written. A malformed later plan refuses the entire
catalog with the existing `invalid_record` diagnostic. The command reads all
recorded plans and introduces no per-call project or plan-size cap.

`part_count` describes the saved plan. It is not a count of completed or available
work. The catalog does not validate runtime part rows or events. After discovery,
use the existing project inspector to validate those rows and inspect readiness,
references and evidence; use the history inspector for recorded events. Listing
a plan does not independently verify its external work or permit replay.

## Save a catalog

~~~sh
python -m fanout_engine.projects --database "work/dispatch.sqlite3" \
  --output saved-projects.json
~~~

`--output` must name a new file in an existing directory. The command validates
and encodes the entire catalog before using the existing exclusive-new-file
publisher. On success the file equals the stdout JSON bytes, and stdout is empty.
Existing files, directories and symlinks are refused unchanged, including the
selected ledger itself. Output failures can retain a complete file if publication
succeeded but cleanup failed; ordinary stream failure can leave a received prefix.
See the [existing-ledger guide](inspect-ledger.md) for the shared output boundary.

| Exit status | Meaning |
| --- | --- |
| 0 | The complete catalog was written and flushed. |
| 1 | Output publication or stream writing failed. |
| 2 | Invalid options, unreadable database, incompatible project table, or invalid recorded plan. No successful catalog was written. |

Diagnostics go to stderr. There is no missing-project status because an empty
catalog is a successful result.

## Python use

~~~python
from fanout_engine import Ledger, inspect_project
from fanout_engine.projects import list_projects

with Ledger.open_readonly("work/dispatch.sqlite3") as ledger:
    catalog = list_projects(ledger)
    for entry in catalog["projects"]:
        report = inspect_project(ledger, entry["project_id"])
        print(entry["project_id"], report["state_counts"])
~~~

Returned dictionaries and lists are detached from stored state. The catalog
query does not open, commit or roll back a transaction on a caller-owned
connection. If that connection has pending changes, ordinary SQLite visibility
applies. A later detailed inspection is a separate snapshot and can observe newer
committed state.

The CLI uses the existing `Ledger.open_readonly` method. It requires an existing
regular file, treats the path as literal filesystem data, opens SQLite with
`mode=ro`, and performs no schema initialization. It retains normal locking and
WAL visibility. Missing files are not created; unreadable or incompatible project
tables are refused. The opener's existing path-replacement and WAL-bookkeeping
limits remain documented in the [existing-ledger guide](inspect-ledger.md).

## Verify locally

~~~sh
python -B -m unittest discover -s tests -p test_projects.py -v
python -B -O -m unittest discover -s tests -p test_projects.py -v
python -B -m unittest discover -s tests -v
~~~

The focused tests cover empty and ordered catalogs, native plan identity,
complete refusal of malformed plans, detached values, one-query observation,
caller transaction preservation, runtime-row scope, actual CLI handoff to the
existing inspector, exclusive output, input refusal, strict options and committed
WAL visibility. All fixtures are authored local data.
