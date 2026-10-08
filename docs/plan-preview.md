# Preview an authored plan

Review a plan's native identity, initial dependency readiness and configured routes before supplying a Ledger or a Hub. The preview runs entirely through the existing Plan and EffortRouter. It does not create dispatch state or submit work.

## Run a complete preview

Save this as **plan.json**:

~~~json
{
  "project": "source-review",
  "parts": [
    {
      "id": "draft",
      "instruction": "Write a draft grounded in the collected references.",
      "depends_on": ["research"]
    },
    {
      "id": "research",
      "instruction": "Collect the public references."
    }
  ]
}
~~~

Save the caller-supplied routing settings as **routes.json**:

~~~json
{
  "catalog": {
    "model-a": ["low", "high"],
    "model-b": ["low", "high"]
  },
  "pool": [
    {"model": "model-a", "effort": "low"},
    {"model": "model-b", "effort": "low"}
  ],
  "explicit_routes": {
    "draft": {"model": "model-b", "effort": "high"}
  },
  "step_up": {"model": "model-b", "effort": "high"}
}
~~~

Run from a checkout, or an environment where this package is installed:

~~~sh
python -m fanout_engine.preview --plan plan.json --routes routes.json
~~~

The command writes one complete JSON document to stdout. To retain it in a new file:

~~~sh
python -m fanout_engine.preview --plan plan.json --routes routes.json --output preview.json
~~~

The destination parent must already exist and the destination must be absent. A successful file export writes no status text to stdout. Existing files, directories and symlinks are refused; choose a new filename for another retained preview.

## Read the report

| Field | Meaning |
| --- | --- |
| schema_version | Version 1 of this preview document. |
| plan | The actual native Plan representation, preserving declaration and dependency order. |
| plan_digest | The digest calculated by the existing Plan implementation. |
| dependency_ready_without_completions | Part IDs returned by native Plan.ready_parts(()) in declaration order. |
| routes | One row per authored part, including parts waiting on dependencies. Each row contains part_id, route, route_source and the native idempotency_key. |
| configured_step_up | The configured model/effort pair, or null. Preview never performs a step-up. |
| input_sha256 | CLI-only hashes of the exact captured plan and routing file bytes. |

For the example, research is initially dependency-ready. The report still includes draft's explicit model-b/high route. A denied explicit route on draft refuses the entire request, even though draft is not initially ready.

The plan digest describes native plan identity. The CLI uses the existing strict JSON parser and Plan.from_dict, including its existing sorted, deduplicated tag normalization. Raw input hashes separately identify the bytes that were read; changing whitespace can change an input hash while preserving the native plan digest. No timestamp or absolute filename is included, so repeating the same captured inputs produces identical report bytes.

Initial dependency readiness contains no evidence about queued, running, completed, failed or unknown stored work. A preview is not a dispatch receipt, worker-capacity observation or proof of provider authorization. The catalog and routes are supplied by the caller. Consult retained Ledger state and the integration's authorization and admission rules before dispatching work.

## Routing input

The routing document has two required fields:

- **catalog:** a nonempty object mapping model strings to nonempty lists of effort strings. Every declared model/effort pair must be a valid native Route, including unused catalog entries.
- **pool:** a nonempty ordered array of route objects. Native EffortRouter performs the existing deterministic selection; pool order and repeated entries retain their native meaning.

Two fields are optional:

- **explicit_routes:** an object mapping this plan's part IDs to route objects. Each explicit route must be in the supplied catalog. Omission or an empty object leaves every choice to the pool.
- **step_up:** a route object or null. Omission means no configured step-up. A supplied route is validated by the native router and reported only as configuration.

Every route object has exactly two string fields, model and effort. Model and effort validation comes from native Route; configured pool, step-up and explicit choices must be allowed by the supplied catalog. Unknown fields, duplicate JSON keys, malformed shapes and unknown explicit part IDs are refused. Preview resolves every part before producing a success document.

## Call the native helper

Use a direct import from the new module:

~~~python
from fanout_engine import EffortRouter, Part, Plan, Route
from fanout_engine.preview import preview_plan

plan = Plan("source-review", (
    Part("draft", "Write the draft.", ("research",)),
    Part("research", "Collect public references."),
))
router = EffortRouter(
    {"model-a": ("low", "high")},
    pool=(Route("model-a", "low"),),
)
report = preview_plan(
    plan,
    router,
    explicit_routes={"draft": Route("model-a", "high")},
)
print(report["plan_digest"])
print(report["dependency_ready_without_completions"])
~~~

The helper accepts an actual native Plan, an actual native EffortRouter and an optional mapping of part IDs to native Route objects. It preserves the identity of an already-constructed Plan instead of reparsing or normalizing it. Its detached JSON-compatible result excludes CLI input hashes because the helper did not read files.

The helper does not accept completed IDs or stored-state fields. Configured routes for blocked parts are still validated, and unknown explicit IDs are errors. It does not call the router's step-up method.

## Bounds and file delivery

The CLI accepts UTF-8 regular files with capped reads:

| Consumer input or output | Limit |
| --- | --- |
| Plan input | 1 MiB (1,048,576 bytes) |
| Routing input | 256 KiB (262,144 bytes) |
| Plan parts | 256 |
| Catalog models | 256 |
| Pool routes | 256 |
| Complete serialized report | 4 MiB (4,194,304 bytes), including its final LF |

The helper also enforces the part and report limits. These limits belong to this consumer; they do not change Plan, the router or the dispatcher. The part bound contains the native recursive DAG validator. Deep or malformed JSON, invalid native plans/routes and I/O errors produce a diagnostic on stderr and exit status 2.

Both inputs and the complete report are validated before output begins. File delivery writes and fsyncs an owned temporary file in the destination parent, then publishes it with a no-clobber hard link. A filesystem that cannot provide that operation returns an error instead of falling back to replacement. A pre-publication failure removes the owned stage and leaves prior files intact. If cleanup fails after publication, the diagnostic states that the report was published; a nonzero exit alone cannot prove that nothing was delivered.

Stdout delivery can fail after a reader has received a prefix, so an I/O error is not a successful complete preview. Captured input hashes identify the bytes used for this invocation; they do not assert that another process could not change the input path later.

## Verification

Run the focused consumer tests or the existing repository suite:

~~~sh
python -m unittest discover -s tests -p test_preview.py -v
python -m unittest discover -s tests -v
~~~

The consumer tests exercise real CLI processes, native API agreement, direct-constructor identity, whole-request refusal, limits, no-clobber delivery and denied connection/spawn operations. POSIX file-size, nonblocking FIFO and /dev/full controls run where the operating system provides those facilities. The existing repository workflow remains unchanged.
