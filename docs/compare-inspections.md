# Compare two saved inspection documents

The saved-inspection reader describes literal differences between two JSON
documents that were already saved. It preserves the complete parsed documents,
identifies their original bytes, and lists changed fields without opening a
ledger or running a project.

Use it when reviewing two observations of the same declared project and plan.
The files can come from separate executions. The reader does not establish that
one observation occurred before the other, or that either observation describes
the current external result.

## Run from the repository checkout

Use Python 3.10 or later, from the repository root. No additional dependency is
needed.

```bash
python3 -B -m fanout_engine.compare_inspections --first ../first-inspection.json --second ../second-inspection.json --output ../saved-inspection-comparison.json
```

Choose a new output path. Open the resulting JSON in an editor or JSON viewer.
Omit `--output` to write the same UTF-8 JSON, with its final newline, to standard
output.

The `first` and `second` labels preserve the order you supplied. They do not mean
earlier and later. For example, a saved `outcome_unknown` value in one file and a
saved `completed` value in the other are reported as those two literal values.
The comparison does not resolve the uncertainty or authorize a retry.

If you need to create an inspection from a retained database, see the existing
[inspection guide](inspect-ledger.md). To open a retained database as an offline
HTML page, use the [project review guide](project-review.md). This command takes
the saved JSON files themselves; it does not take HTML pages or database files.

## What is in the result

The report uses schema `fanout.saved-inspection-comparison/1` and sets
`saved_data_only` to `true`.

| Field | Meaning |
| --- | --- |
| `first`, `second` | Each side's complete parsed `document`, original `input_bytes` count and original `input_sha256`. |
| `same_input_bytes` | Whether the complete original byte sequences are identical. |
| `same_saved_values` | Whether all parsed values are equal under the comparison rules below. |
| `part_order_changed` | Whether the part ID sequence differs between the documents. |
| `top_level_changes` | Changed top-level fields, excluding `parts`, sorted by field name. |
| `changed_part_ids` | Parts with changed fields, listed in the first document's part order. |
| `part_changes` | Each changed `part_id` and its changed `fields`, sorted by field name within that part. |

A changed field records a `first` and `second` side. Each has `present`; a present
field also has `value`. Thus an absent field and a field whose value is JSON
`null` remain distinct:

```json
{
  "field": "artifact_ref",
  "first": {"present": false},
  "second": {"present": true, "value": null}
}
```

Unrecognized fields remain in the complete documents and participate in the
comparison. Nested objects and arrays are retained as complete field values,
rather than flattened into paths. The reader does not drop timestamps, evidence,
routes, task references, or state labels.

## Equality and ordering

Object key order and JSON whitespace do not affect saved-value equality. They
can still change the original byte counts, hashes and `same_input_bytes`.

Array order matters, including the order of `parts`. Parts are matched by their
IDs to produce field changes, so reordering otherwise identical parts sets
`part_order_changed` and makes `same_saved_values` false, while leaving
`part_changes` empty.

The reader distinguishes JSON booleans from integers, integers from floating
point values, and floating `-0.0` from `0.0`. It uses Python's strict JSON parser
and canonical serializer. The two integer spellings `-0` and `0` both parse as
integer zero; their spelling difference remains visible only in raw input
identity. Other lexical differences that parse to the same value likewise do
not become field changes. Finite floating point numbers use Python's numeric
representation; this is not an arbitrary-precision decimal comparison.

Fields are sorted by Python string order. Changed parts follow the first
document's part order. Swapping the inputs swaps their roles and can therefore
change the order of part-change rows. No timestamp sorting or subtraction is
performed.

## Input shape and declared relationship

Each input must be a complete regular file referent of at most 1 MiB. A symlink
to a regular file is accepted. JSON must use UTF-8, have no duplicate object
keys, contain finite numbers and be encodable as UTF-8 after parsing.

Each top-level document must be an object with:

- A nonempty string `project_id`.
- A nonempty string `plan_digest`.
- A `parts` array of at most 256 objects, each with a unique nonempty string `id`.

The two documents must declare the same project ID, plan digest and complete
set of part IDs. Empty part arrays are accepted. Strings are not trimmed, and
the reader does not apply the native plan's identifier grammar. Additional
fields and unknown saved state values are accepted.

These are structural checks for comparison. They do not validate a native plan,
authenticate the supplied digest, prove the documents' origin, or verify
external work. Keep the source labels and provenance of the saved files with
the result.

The complete serialized comparison, including both documents and all changed
field values, is limited to 8 MiB. A valid input pair can exceed that output
limit when many fields change; the reader refuses the complete comparison
instead of emitting a partial report.

## Output and failure behavior

| Exit status | Meaning |
| --- | --- |
| `0` | Complete comparison written. Differences do not cause a failure exit. |
| `2` | Invalid arguments, unreadable input, invalid JSON or shape, mismatched declared relationship, excessive nesting, or an oversized complete comparison. |
| `1` | The comparison was formed but its output could not be written. |

Input files are read without rewriting them. File output uses the existing
create-new publication helper, so an occupied output path, either input path,
or a dangling symlink destination is refused. Its parent directory must already
exist. The helper uses a temporary file and a hard link in that directory; an
underlying filesystem that does not support that publication operation can
refuse it. After a successful file write, standard output is empty.

Input or comparison failures create no report file. Diagnostics go to standard
error. A failed standard-output write can leave a prefix with its receiver.
If publication succeeds but temporary-file cleanup fails, the command reports
an output failure even though the destination may already contain the complete
report; inspect that file before choosing a new output path.

## Focused verification

```bash
python3 -B -m unittest discover -s tests -p 'test_compare_inspections.py' -v
```

The maintained tests exercise saved-value distinctions, ordering, admission and
complete-output limits, actual CLI output, occupied destination refusal, input
conservation, regular-file referents, and explicit file output when standard
output is unavailable.

## Open the comparison as an offline page

Use the same saved JSON inputs and select HTML explicitly:

```bash
python3 -B -m fanout_engine.compare_inspections --first ../first-inspection.json --second ../second-inspection.json --format html --output ../saved-inspection-comparison.html
```

Open the new HTML file in a browser. It contains the equality and part-order
flags, complete input hashes and byte counts, every changed top-level and part
field, and expandable complete First and Second documents. On a narrow screen,
field sides stack with explicit First and Second labels.

Each changed side is displayed as its complete JSON object, including
`present` and, when present, `value`. Absence and present/null remain distinct.
The native comparison determines row order and value distinctions; HTML adds no
inference about chronology, progress, authority or whether external work succeeded.

**Download exact comparison JSON** saves the complete native comparison report,
including its final newline. The embedded download uses the same bytes as default
JSON output and explicit `--format json`. Displayed data uses literal JSON notation
and HTML escaping. C0 controls use JSON escapes; DEL/C1 controls and bidi
formatting controls are shown as Unicode escapes. Ordinary Unicode letters,
Arabic/Hebrew text and emoji joiners remain intact. Authored literal backslash
sequences remain distinguishable from control escapes. These display choices do
not alter the native JSON download or either input.

The page is self-contained, with no scripts or external resources. A browser is
sufficient to read the saved result; no server or installed engine is needed.
It does not update observations, open a ledger or rerun work.

HTML is limited to 32 MiB after complete rendering, in addition to the existing
8 MiB native JSON limit. An oversized HTML report is refused with exit status 2
before publication. The same create-new output rules and output-failure status
1 apply to both formats. Omit `--output` to write the selected format to stdout;
file extensions do not select a format.

Run the focused HTML tests alongside the existing JSON-reader tests:

```bash
python3 -B -m unittest discover -s tests -p 'test_compare_inspections*.py' -v
```
