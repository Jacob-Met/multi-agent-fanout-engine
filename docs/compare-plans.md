# Compare two plan drafts

The ledger accepts an identical plan again, but refuses a changed plan under an
existing project ID. Compare two drafts before choosing how to proceed:

```sh
python -m fanout_engine.compare --before original.json --after revised.json
```

The command reads both authored files and writes one complete JSON comparison.
It shows full native plans and digests, added and removed parts, exact edits to
retained parts, declaration-order changes, and every before/after idempotency
key. It uses Python 3.10+ and the standard library. Run from the repository root
or an environment where the package is installed.

## Try a complete comparison

Save this as `original.json`:

```json
{
  "project": "source-review",
  "parts": [
    {"id": "research", "instruction": "Collect the public references."},
    {"id": "draft", "instruction": "Write the draft.", "depends_on": ["research"]}
  ]
}
```

Save this as `revised.json`:

```json
{
  "project": "source-review",
  "parts": [
    {"id": "research", "instruction": "Collect the public references."},
    {"id": "draft", "instruction": "Write the draft with source citations.", "depends_on": ["research"]},
    {"id": "review", "instruction": "Review the cited draft.", "depends_on": ["draft"]}
  ]
}
```

Run the command above. The result includes:

- `same_plan: false` and `project_id_changed: false`.
- `added_part_ids: ["review"]` and an empty removed list.
- A `changed_parts` row for `draft`, with `fields: ["instruction"]`.
- `part_order_changed: true`, because the complete sequence of declared IDs now
  includes `review`.
- Changed keys for both retained IDs, including the unchanged `research` part.

Native keys include the complete plan digest. An edit anywhere in the native
plan changes the keys for its retained parts, even when their own payload is
unchanged. Changing only the project ID or declaration order also changes the
native digest and keys. A comparison exposes these consequences; it does not
choose a new project ID, update stored rows or decide whether work can be
submitted again.

To save the JSON safely, select a new output file:

```sh
python -m fanout_engine.compare --before original.json --after revised.json --output comparison.json
python -m json.tool comparison.json
```

The `--output` path must not already exist; an existing file, directory,
symlink or either input path is refused instead of overwritten. Both input
files are validated and the entire JSON report is encoded before the output
is published. The CLI stages the complete bytes beside the destination,
flushes and syncs them, then uses an exclusive hard link to publish a new
file. Existing files and input bytes are left intact even when publication
fails. A failed cleanup may leave a staging file; this is not a general
crash-durability or multi-file transaction guarantee. Without `--output`,
the original stdout behavior remains unchanged. Shell `>` redirection
continues to follow ordinary replacement rules and should not be used for
exclusive publication.

## Read the comparison

| Field | Meaning |
| --- | --- |
| `schema_version` | Version 1 of this comparison document. |
| `before`, `after` | Each contains the complete native `plan` and its `plan_digest`. |
| `same_plan` | Whether the two complete native plan documents are equal. |
| `project_id_changed` | Whether their exact project IDs differ. |
| `part_order_changed` | Whether the complete ordered lists of part IDs differ; additions and removals also change these lists. |
| `added_part_ids` | IDs present only after the edit, in after declaration order. |
| `removed_part_ids` | IDs present only before the edit, in before declaration order. |
| `changed_parts` | Retained IDs whose `instruction`, `depends_on` or `tags` values differ, in after declaration order. `fields` names each changed field; full values are in the two plans. |
| `idempotency_keys` | One row per ID, with `before`, `after` and `changed`. A missing side is `null`. After IDs appear first in declaration order, then removed IDs in before declaration order. |
| `input_sha256` | CLI-only hashes of the exact input bytes captured for each side. |

Changes are directional: reversing the inputs exchanges additions and removals
and the before/after values. Instructions, dependency order and native tag
values are compared exactly. The CLI constructs both plans through the existing
strict parser and `Plan.from_dict`, which sorts and deduplicates input tags.
Thus formatting, object-key order and repeated input tags can produce different
raw input hashes while leaving `same_plan` true and all native keys unchanged.

No timestamp or absolute input path is added. Repeating identical captured
inputs produces identical report bytes. The hashes identify captured bytes;
they do not promise that another process cannot later change an input file.

The report describes the supplied drafts. Use the
[retained-ledger inspector](inspect-ledger.md) for observed stored states and
evidence, or the [plan preview](plan-preview.md) for caller-supplied routes.
Comparison does not open a database, contact a Hub, reserve work or perform a
state transition.

## Use the native helper

```python
from fanout_engine import Part, Plan
from fanout_engine.compare import compare_plans

before = Plan("review", (Part("draft", "Write the draft."),))
after = Plan("review", (Part("draft", "Write the cited draft."),))
report = compare_plans(before, after)
print(report["changed_parts"])
```

The helper accepts native Plans and returns detached JSON-compatible data.
It captures and validates an owned native snapshot of each input, preserving
direct-constructor dependency order and repeated tags. If a historically
admitted mutable Part-like object has changed since its Plan was validated, the
captured digest no longer agrees and the helper raises `ComparisonError`.
It does not modify either supplied Plan. CLI byte hashes are absent because the
helper did not read files.

## Limits and exit statuses

Each CLI input must be a UTF-8 regular file at most 1 MiB. File paths are literal
filesystem names; quote names containing spaces or shell punctuation. Each
plan can contain at most 256 parts. The complete serialized report, including
its final newline and CLI hashes, can be at most 4 MiB. The helper also enforces
the part and report limits. These are limits of this comparison consumer.

Both complete plans and the report are validated before successful output
begins. Invalid graphs, duplicate JSON keys, non-finite numbers, unsupported
fields, malformed UTF-8, excessive nesting and unreadable inputs are refused.
A missing input or parent is not created. On systems providing nonblocking
opens, named pipes are refused without waiting for a writer.

| Status | Meaning |
| --- | --- |
| `0` | A complete comparison was written and flushed, whether or not differences exist. |
| `1` | Report output failed; a receiving stream may contain a prefix. |
| `2` | Invalid command options, inputs or comparison limits. No comparison is written. |

Diagnostics go to stderr. Ordinary interpreter and operating-system termination
remain outside these controlled statuses.

## Verification

```sh
python -B -m unittest discover -s tests -p test_compare_plans.py -v
python -B -m unittest discover -s tests -v
```

The focused tests receive full native/API/CLI agreement, independent key
derivation, changed project and declaration order, input normalization,
direct-constructor identity, stale mutable-input refusal, literal filenames,
unchanged source files, malformed second-input refusal and actual limits.
Nonblocking FIFO and `/dev/full` controls run where available. The tests use
authored local data and do not call a remote adapter.
