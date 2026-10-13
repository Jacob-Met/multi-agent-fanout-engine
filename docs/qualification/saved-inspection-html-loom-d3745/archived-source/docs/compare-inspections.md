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

## Read the saved comparison as an offline page

Add an explicit HTML format when the recipient needs to read the captured
differences in a browser:

```sh
python -B -m fanout_engine.compare_inspections \
  --first first-inspection.json --second second-inspection.json \
  --format html --output saved-comparison.html
```

Open the newly created HTML file directly. It needs no server, network,
JavaScript or installation in the browser. The page puts three summary facts,
the exact captured input identities, complete changed-field envelopes and both
complete parsed documents together. The complete documents use ordinary
expandable sections. Narrow windows stack each field's first and second sides.

The labels **first** and **second** identify the arguments. They do not establish
chronology, prove a state transition or resolve an unknown outcome. A pure
part-array reorder is reported separately even if no part fields changed.
The prominent saved-data notice retains the same structural-only comparison
boundary as the JSON report.

Each changed side is shown as its full JSON envelope. An absent field is
`{"present": false}`; a present null has
`{"present": true, "value": null}`. Booleans, integer and floating forms,
signed floating zero, arrays and complete nested values remain visible.
Authored markup stays literal text. Ordinary Unicode remains readable; DEL,
C1 controls and the twelve bidi formatting characters U+061C, U+200E–U+200F,
U+202A–U+202E and U+2066–U+2069 are visibly escaped in this display.
This presentation treatment does not change either source document or the
download.

**Download exact comparison JSON** is a single ordinary embedded data link.
It contains byte-for-byte the canonical comparison that the original JSON
command emits, including both documents, their raw input hashes/byte counts
and the final LF. Browser download restrictions are host behavior; the
ordinary JSON file command remains available.

Default output and explicit `--format json` have identical native JSON bytes.
HTML stdout and file output are deterministic for the same admitted input
bytes. The native 8 MiB complete-comparison limit is checked first; the
complete HTML then has a separate 32 MiB limit before any publication.
An HTML size refusal exits 2. File or stdout write failures retain exit 1;
a failed stdout sink may already have received a prefix.

Both formats use the same exclusive new-file publisher and preserve its
occupied destination, input path, dangling symlink and absent-parent
behavior described above. No output directories are created. Do not
interpret a late publication/cleanup failure as a guarantee that no
destination was written; inspect a retained destination before choosing a
new path.

Focused presentation controls:

```sh
python3 -B -m unittest discover -s tests -p 'test_compare_inspections_html.py' -v
python3 -O -B -m unittest discover -s tests -p 'test_compare_inspections_html.py' -v
```

The presentation tests call the actual CLI, preserve exact native downloads,
exercise typed/absent values and passive escaping, distinguish identical and
order-only documents, and check bounded publication failures. Their CLI
children inherit optimized execution when the test parent uses `-O`.
