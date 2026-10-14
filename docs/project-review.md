# Hand off a retained project as an offline review

The inspection JSON remains the native record. The separate review command makes
that same validated snapshot readable as a self-contained HTML page:

```sh
python -m fanout_engine.review --database work/dispatch.sqlite3 \
  --project sample --output work/sample-review.html
```

Choose an existing ledger, its exact project ID and a new output filename. Find
IDs with `python -m fanout_engine.projects --database work/dispatch.sqlite3`.
The command needs Python 3.10 or newer and the standard library, with the package
available through the checkout or an existing installation. It exits silently
on success. Open the resulting HTML in an ordinary browser; no server, network,
JavaScript or browser storage is needed. Keep it with the other review artifacts.

## What the reader receives

The page shows all six native state counts, observed queued-ready and blocked IDs,
and a linked table of every part in original declaration order. Each part retains
its full instruction, tags, declared and direct unmet dependencies, native state,
worker and task references, route, artifact reference, evidence, recorded update
timestamp and idempotency key. Expand **Complete recorded part** for its full
native JSON object. Keyboard navigation and the browser's text search are useful
for larger reports. Printing keeps the visible details; expand a complete-object
panel first if you also want that repeated JSON in the printout.

**Download exact inspection JSON** contains exactly the existing inspection CLI's
serialization of this captured report: UTF-8 `canonical_json(report)` followed by
one LF. The download travels inside the HTML, so moving the page does not lose its
native data. Given the same captured report, the HTML bytes are deterministic;
there is no fabricated capture timestamp or machine-specific source path in it.

Markup in instructions and evidence is displayed literally. C0 controls other
than tab, LF and CR, and the DEL/C1 controls, are shown as backslash Unicode
escapes in the page. Unicode bidirectional formatting controls U+061C,
U+200E/U+200F, U+202A–U+202E and U+2066–U+2069 also appear as visible
backslash Unicode escapes. This exposes otherwise invisible direction marks,
embeddings, overrides and isolates in accepted instruction, reference, route
and evidence text. Ordinary Arabic/Hebrew letters and other Unicode, including
emoji joiners, keep their original text. The embedded native JSON preserves the
original values, including every formatting control.
References and evidence locators remain text rather than links to external sites.
They are not opened or authenticated by the report. `null` means no value was
recorded, not a successful or empty external result.

## Preserve the meaning of the snapshot

Ready means recorded queued state with completed direct prerequisites. It is not
a dispatch reservation, a route or worker availability check, or proof about
external work. Failed prerequisites remain failed; unknown outcomes remain
unknown. Dispatching rows are not recovered or marked unknown. The page performs
no dispatch, retry, recovery or reconciliation. A later ledger change requires a
new report, and the reader should retain the intended database/command separately
when that provenance matters. The plan digest is a recorded content identity,
not authentication of the database or operator.

The command uses the unchanged native `inspect_project` snapshot validation and
`Ledger.open_readonly` behavior. It validates the complete captured project before
constructing or publishing any output. Missing parts, malformed JSON or conflicting
plan/payload/key identities refuse the whole report. Ordinary SQLite locking and
WAL visibility remain in force; it is not an immutable filesystem snapshot and
does not initialize or repair a ledger.

## Output and exit status

The complete HTML is prepared before the existing exclusive new-file publisher is
called. Existing output files, links and directories are refused. The selected
SQLite database and its reserved `-wal`, `-shm` and `-journal` destinations are
protected through the same path guard as the inspection exporter. Parent output
directories must already exist. This does not coordinate concurrent writers or
provide a transaction with other files. Source data and native recorded state
are not changed by this consumer.

| Exit | Meaning |
| --- | --- |
| 0 | A complete new HTML report was published. |
| 1 | Output could not be published; inspect the diagnostic and destination. |
| 2 | Invalid command arguments, unreadable database or invalid retained record. |
| 3 | The selected project is not in the ledger. |

The Python helper returns HTML bytes without publishing them:

```python
from fanout_engine.ledger import Ledger
from fanout_engine.review import review_project

with Ledger.open_readonly("work/dispatch.sqlite3") as ledger:
    html_bytes = review_project(ledger, "sample")
```

The caller retains responsibility for any later publication of those bytes. A
plain Python write does not acquire the CLI's exclusive-output safeguards.

## Maintained receiving

```sh
python -B -m unittest discover -s tests -p test_project_review.py -v
python -O -B -m unittest discover -s tests -p test_project_review.py -v
```

The course uses authored local SQLite state, real CLI subprocesses, all six native
states, exact embedded JSON, literal Unicode/markup/control text, original part
order, deterministic output, missing and malformed records, existing-output
preservation and reserved SQLite paths. It does not qualify an external adapter,
an installed estate deployment or the truth of retained evidence.

The focused display regression uses the same actual CLI over fictional retained
plans, with all twelve formatting controls, exact native JSON bytes and ordinary
RTL/Unicode/joiner controls:

```sh
python -B -m unittest discover -s tests -p test_project_review_bidi.py -v
python -O -B -m unittest discover -s tests -p test_project_review_bidi.py -v
```

The optimized runner propagates `-O` to its CLI subprocesses. These checks cover
the displayed text and unchanged native download, not a full Unicode shaping or
browser accessibility audit.
