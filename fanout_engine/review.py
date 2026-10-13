"""Save a self-contained offline review of one validated retained project."""
from __future__ import annotations

import argparse
import base64
import html
import json
from pathlib import Path
import sqlite3
import sys

from .inspect import _check_output_path
from .inspection import InspectionError, inspect_project
from .ledger import Ledger, LedgerError
from .plan import canonical_json
from .preview import PreviewError, _publish_new_file


def _text(value: str) -> str:
    """Keep markup literal and make non-printing HTML controls visible."""
    visible = "".join(
        f"\\u{ord(character):04x}"
        if (ord(character) < 32 and character not in "\t\n\r")
        or 127 <= ord(character) <= 159 else character
        for character in value
    )
    return html.escape(visible, quote=True)


def _json(value: object) -> str:
    return _text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2))


_STYLE = """
:root { color-scheme: light; font-family: system-ui, sans-serif; color: #182f35; background: #f4f5f0; }
* { box-sizing: border-box; }
body { margin: 0; line-height: 1.55; }
main { max-width: 1100px; margin: 0 auto; padding: 2rem 1.25rem 4rem; }
header { border-top: 5px solid #146b63; padding-top: 1rem; margin-bottom: 2rem; }
h1 { font-size: clamp(1.8rem, 4vw, 2.8rem); line-height: 1.2; margin: .5rem 0; overflow-wrap: anywhere; }
h2 { margin-top: 2rem; } h3 { margin: 0; font-size: 1.3rem; overflow-wrap: anywhere; }
a { color: #075e61; text-underline-offset: .2em; }
a:focus-visible, summary:focus-visible { outline: 3px solid #b35b00; outline-offset: 4px; }
.eyebrow { font-size: .8rem; letter-spacing: .12em; text-transform: uppercase; font-weight: 700; }
.download { display: inline-block; padding: .65rem 1rem; border: 1px solid #146b63; border-radius: .4rem; font-weight: 650; }
.counts { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: .65rem; }
.count, article { background: white; border: 1px solid #ccd8d2; border-radius: .5rem; padding: 1rem; }
.count strong { display: block; font-size: 1.7rem; }
.count span, .state { overflow-wrap: anywhere; }
.note { border-left: 4px solid #bb8b41; padding: .6rem 1rem; background: #fff8e9; }
.scroll { overflow-x: auto; } table { width: 100%; border-collapse: collapse; background: white; }
th, td { text-align: left; vertical-align: top; padding: .75rem; border-bottom: 1px solid #ccd8d2; }
th { background: #e9efeb; } td { overflow-wrap: anywhere; }
article { margin-top: 1rem; } .state { font-weight: 650; color: #3c5860; }
pre { font: .9rem/1.55 ui-monospace, monospace; white-space: pre-wrap; overflow-wrap: anywhere; margin: .45rem 0 1rem; }
code { overflow-wrap: anywhere; } dl { margin: 0; } dt { font-weight: 650; margin-top: .8rem; } dd { margin: .2rem 0 1rem; }
summary { cursor: pointer; font-weight: 650; padding: .5rem 0; }
footer { margin-top: 2rem; border-top: 1px solid #ccd8d2; padding-top: 1rem; }
@media print { :root { background: white; } main { max-width: none; padding: 0; } .download { display: none; } article { break-inside: avoid; } }
"""


def review_project(ledger: Ledger, project_id: str) -> bytes:
    """Render the unchanged native inspection snapshot as offline UTF-8 HTML.

    The embedded JSON is byte-for-byte the canonical inspection CLI encoding,
    including its final LF. This function does not publish files or open locators.
    """
    report = inspect_project(ledger, project_id)
    document = (canonical_json(report) + "\n").encode("utf-8")
    download = base64.b64encode(document).decode("ascii")
    counts = "".join(
        f'<div class="count"><strong>{count}</strong><span>{_text(state).replace("_", "_<wbr>")}</span></div>'
        for state, count in report["state_counts"].items()
    )
    rows = []
    cards = []
    for index, part in enumerate(report["parts"]):
        unmet = ", ".join(f'{dependency["id"]} ({dependency["state"]})'
                          for dependency in part["unmet_dependencies"])
        rows.append(
            f'<tr><th scope="row"><a href="#part-{index}">{_text(part["id"])}</a></th>'
            f'<td>{_text(part["state"])}</td>'
            f'<td>{_text(unmet) if unmet else "None recorded"}</td></tr>'
        )
        fields = "".join(
            f'<dt>{label}</dt><dd><pre>{_json(part[key])}</pre></dd>'
            for label, key in (
                ("Tags", "tags"), ("Declared dependencies", "depends_on"),
                ("Direct unmet dependencies", "unmet_dependencies"),
                ("Worker reference", "worker_id"), ("Task reference", "task_id"),
                ("Recorded route", "route"), ("Artifact reference", "artifact_ref"),
                ("Recorded evidence", "evidence"), ("Recorded update timestamp", "updated_at"),
                ("Idempotency key", "idempotency_key"),
            )
        )
        cards.append(
            f'<article id="part-{index}"><h3>{_text(part["id"])}</h3>'
            f'<p class="state">{_text(part["state"])}</p>'
            f'<h4>Instruction</h4><pre>{_text(part["instruction"])}</pre>'
            f'<dl>{fields}</dl><details><summary>Complete recorded part</summary>'
            f'<pre>{_json(part)}</pre></details></article>'
        )
    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Retained project · {_text(report["project_id"])}</title>
<style>{_STYLE}</style></head><body><main>
<header><p class="eyebrow">Fanout · Retained project review</p>
<h1>{_text(report["project_id"])}</h1>
<p>A captured ledger observation. This page does not update itself or perform work.</p>
<p>Plan digest</p><pre>{_text(report["plan_digest"])}</pre>
<a class="download" download="project-inspection.json" href="data:application/json;base64,{download}">Download exact inspection JSON</a>
</header>
<section aria-labelledby="states"><h2 id="states">Recorded states</h2><div class="counts">{counts}</div></section>
<section aria-labelledby="readiness"><h2 id="readiness">Observed dependency readiness</h2>
<dl><dt>Queued and dependency-ready IDs</dt><dd><pre>{_json(report["queued_ready_ids"])}</pre></dd>
<dt>Blocked queued IDs</dt><dd><pre>{_json(report["blocked_queued_ids"])}</pre></dd></dl>
<p class="note">Ready means recorded queued state with completed direct prerequisites. It is not a dispatch reservation, a route or worker availability check, or proof about external work. Unknown outcomes remain unknown; dispatching work is not recovered by this review.</p>
</section>
<section aria-labelledby="parts"><h2 id="parts">Parts in authored order</h2>
<div class="scroll"><table><thead><tr><th scope="col">Part</th><th scope="col">State</th><th scope="col">Direct unmet prerequisites</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
{"".join(cards)}</section>
<footer><p>References, routes, evidence and timestamps are retained records. Locators are displayed as text; this page does not open or authenticate them. A null value means no value was recorded. Non-printing control characters appear as backslash escapes; the downloaded JSON preserves the original native values.</p>
<p>The complete project was validated before this report was produced. Later ledger changes require a new report. No adapter call, dispatch, retry, reconciliation, provider request or browser storage operation occurs here.</p></footer>
</main></body></html>
'''
    return page.encode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--database", type=Path, required=True, help="existing SQLite ledger file")
    parser.add_argument("--project", required=True, help="exact recorded project identifier")
    parser.add_argument("--output", type=Path, required=True, help="new self-contained HTML file")
    args = parser.parse_args(argv)
    try:
        with Ledger.open_readonly(args.database) as ledger:
            content = review_project(ledger, args.project)
    except InspectionError as exc:
        print(f"fanout review: {exc.code}: {exc}", file=sys.stderr)
        return 3 if exc.code == "project_not_found" else 2
    except (LedgerError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"fanout review: cannot read ledger: {exc}", file=sys.stderr)
        return 2
    try:
        _check_output_path(args.database, args.output)
        _publish_new_file(args.output, content)
    except (OSError, PreviewError, ValueError) as exc:
        print(f"fanout review: cannot write report: {exc} (output: {args.output})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
