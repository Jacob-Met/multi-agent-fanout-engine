# Reuse selected authored parts with their prerequisites

The `fanout_engine.subplan` command produces a complete ordinary Plan from exact
selected part IDs. It includes every transitive prerequisite once and keeps the
source's declaration order, instructions, dependency order and native tag values.
An unrelated branch is left out. A shared prerequisite remains a single part.

This is useful when a larger authored plan contains a smaller piece of work you
want to reuse. Copying only the final part can leave missing dependencies: the
native Plan constructor correctly refuses that incomplete document. This producer
collects the required source rows and passes the complete result through that
same native validation.

## Produce a native plan

Save the following authored example as `whole.json`:

```json
{
  "project": "Whole",
  "parts": [
    {"id": "publish", "instruction": "Publish the approved result.", "depends_on": ["review"]},
    {"id": "unrelated", "instruction": "Prepare a different deliverable."},
    {"id": "research", "instruction": "Read the source."},
    {"id": "review", "instruction": "Review the draft.", "depends_on": ["research"]}
  ]
}
```

From a checkout containing this module, run:

```sh
python -m fanout_engine.subplan --plan whole.json --part publish --project Selected > selected.json
```

Use a new destination name for the shell redirection. The command itself writes
stdout; the shell opens or truncates its redirection destination before Python
reads the source. Never redirect onto `whole.json`.

The produced JSON is a native Plan document with exactly `project` and `parts`:

```json
{
  "project": "Selected",
  "parts": [
    {"id": "publish", "instruction": "Publish the approved result.", "depends_on": ["review"], "tags": []},
    {"id": "research", "instruction": "Read the source.", "depends_on": [], "tags": []},
    {"id": "review", "instruction": "Review the draft.", "depends_on": ["research"], "tags": []}
  ]
}
```

The actual output is compact canonical JSON followed by one newline. It retains
`publish, research, review` in source order, even though `research` is the only
initially dependency-ready part. The command does not sort the result into a new
execution order. Selecting both `publish` and `research` produces that same plan:

```sh
python -m fanout_engine.subplan --plan whole.json --part publish --part research --project Selected
```

Repeat `--part` for each desired part. Request order does not change declaration
order. Every selection must be an exact, case-sensitive source ID; an empty
selection, repeated requested ID or unknown ID is refused. Explicitly selecting
a prerequisite already included by another selection is allowed, provided the
request does not repeat that ID. Selecting every source part copies the complete
authored plan under the new project ID.

## Receive the output through existing consumers

`selected.json` is directly admitted by `Plan.from_dict`. It can be used as the
ordinary input to the existing offline preview command. For example, save
`routes.json`:

```json
{
  "catalog": {"authored-offline": ["high"]},
  "pool": [{"model": "authored-offline", "effort": "high"}]
}
```

Then inspect native identities, dependency readiness and the explicit fixture
route without submitting work:

```sh
python -m fanout_engine.preview --plan selected.json --routes routes.json
```

The output is an authored draft. A distinct project ID is required and must pass
the existing native identifier rules. That requirement changes the complete
plan identity and every native idempotency key. It does not establish that the
project ID is unused anywhere: the command does not inspect a ledger. Ordinary
ledger admission remains authoritative if a caller later records the plan.

Completed work, task IDs, selected runtime routes, approvals, artifacts and
unknown outcomes are not transferred. A prerequisite is retained even if work
with a similar ID completed somewhere else. Recording this new plan through the
existing Ledger creates the ordinary initially queued parts. The producer does
not record, dispatch, reconcile or reserve any work.

## Python API

```python
from fanout_engine.subplan import select_subplan

selected = select_subplan(original_plan, ["publish", "research"], "Selected")
```

The helper takes a native `Plan`, a nonempty `Sequence[str]` of selected IDs and
the explicit new project ID. A string, bytes, set or iterator is not the selection
sequence. It returns a detached native Plan whose parts are freshly captured
native `Part` values. The result does not alias mutable Part-like source fields.

The complete source is captured and revalidated before selection. A malformed
unselected part still refuses the request. The captured digest must equal the
supplied Plan's digest, so historically admitted mutable Part-like inputs that
changed after validation are refused instead of silently producing a plan from
stale identity. This is the producer's own admission rule; existing Plan behavior
is unchanged. No concurrent mutation snapshot is promised for arbitrary objects
with stateful attributes.

Direct API construction preserves repeated tags and dependency order exactly.
The file CLI uses the existing `strict_json_loads` and `Plan.from_dict` behavior:
tags are sorted and deduplicated, omitted dependency/tag lists become empty, and
malformed fields, duplicate JSON keys and non-finite numbers are refused. It does
not add a second interpretation of the source format.

## Complete-output bounds and failures

| Boundary | Contract |
| --- | --- |
| Input file | One explicit regular UTF-8 file, at most 1 MiB |
| Source Plan | At most 4,096 parts, including unselected parts |
| Explicit selection | Between 1 and 256 unique known IDs |
| Complete dependency closure | At most 256 parts, matching the existing preview consumer limit |
| Produced native JSON | At most 1 MiB, including its final newline |
| Exit 0 | Complete native plan written successfully |
| Exit 1 | Stdout write or flush failed; a consumer may have received a prefix |
| Exit 2 | Invalid arguments, input, selection, identity or consumer limits; no plan emitted |

The source-part, selection, closure and result-byte limits apply to the Python
helper too. The input-file byte limit applies to the CLI's captured file. The
helper does not impose a source byte limit on an already constructed Plan.

Paths are literal filesystem names. The CLI validates the opened object's type
and caps its actual read; it does not wait on a named pipe on systems supporting
nonblocking opens. It parses and validates the complete input and serializes the
complete result before writing stdout. Bad hidden rows, excessive JSON nesting,
invalid Unicode, unknown selections or an oversized closure never yield a partial
accepted plan. The source is opened read-only and is not rewritten. There is no
new dependency, service, account, model or GitHub Actions requirement.

## Verification boundary

The original native omission witness and the manually completed positive control
are preserved separately with the receiving evidence. The source addition is
three files: this guide, `fanout_engine/subplan.py` and `tests/test_subplan.py`.
Existing Plan, preview, ledger, dispatcher, routing, comparison and workflow
implementations remain unchanged.

Focused checks cover shared ancestors and exact order/fields; detached capture
and stale hidden source; native preview, independent digest/key calculation and
SQLite recording/reopening; a 4,096/4,097 source boundary and a deep 256/257-part
closure; actual CLI input/output byte limits, literal filenames and refusal
before stdout. Nonregular input and an actual full output device are exercised
where the host provides them. Runtime qualification and independent review pins
are recorded in the accompanying receiving evidence, not inferred from these
authored fixtures.
