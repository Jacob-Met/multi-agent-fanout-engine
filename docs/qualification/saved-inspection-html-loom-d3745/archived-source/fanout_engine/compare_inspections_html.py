"""Passive HTML presentation of an admitted saved-inspection comparison."""
from __future__ import annotations

import base64
from html import escape
import json
from typing import Any

MAX_HTML_BYTES = 32 * 1024 * 1024

_STYLE = """
:root { font-family: system-ui, sans-serif; color: #182934; background: #edf2f3; color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; }
main { max-width: 1160px; margin: auto; padding: 36px 24px 64px; }
header { border-top: 6px solid #16756e; padding-top: 24px; }
.eyebrow { color: #286961; text-transform: uppercase; letter-spacing: .09em; font-size: .8rem; font-weight: 700; }
h1 { font-size: clamp(1.9rem, 4vw, 2.7rem); line-height: 1.12; margin: 10px 0 18px; }
h2 { font-size: 1.35rem; margin: 0 0 18px; }
h3 { font-size: 1.05rem; margin: 24px 0 10px; }
p, li, dt, dd, summary { line-height: 1.55; }
p { max-width: 84ch; }
.notice { background: #fff6dc; border-left: 4px solid #8d6400; padding: 12px 16px; }
section { margin-top: 24px; padding: 24px; background: #fff; border: 1px solid #bfcdd0; border-radius: 10px; }
.facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 0; }
.facts div { padding: 14px; background: #f1f7f6; border-radius: 6px; }
dt { color: #3e535c; font-size: .9rem; }
dd { font-size: 1.4rem; font-weight: 650; margin: 5px 0 0; }
table { width: 100%; table-layout: fixed; border-collapse: collapse; margin-top: 14px; }
caption { text-align: left; font-weight: 650; margin: 0 0 10px; overflow-wrap: anywhere; }
th, td { text-align: left; vertical-align: top; padding: 12px; border: 1px solid #cbd6d8; overflow-wrap: anywhere; }
th { background: #eef4f4; font-size: .9rem; }
thead th:first-child { width: 24%; }
pre, code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .85rem; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; word-break: normal; }
pre { margin: 0; }
details { margin-top: 16px; border: 1px solid #cbd6d8; border-radius: 6px; background: #f8fbfb; }
summary { cursor: pointer; font-weight: 650; padding: 14px; }
details pre { padding: 0 16px 16px; }
a { color: #075d72; overflow-wrap: anywhere; text-underline-offset: 3px; }
a:focus-visible, summary:focus-visible { outline: 3px solid #a56700; outline-offset: 4px; }
.download { display: inline-block; padding: 12px 16px; border-radius: 6px; background: #126b65; color: white; font-weight: 650; text-decoration: none; }
.note { color: #485e67; font-size: .9rem; }
@media (max-width: 640px) {
  main { padding: 24px 12px 40px; }
  section { padding: 18px 12px; }
  .facts { grid-template-columns: 1fr; }
  .comparison, .comparison tbody, .comparison tr, .comparison th, .comparison td { display: block; width: 100%; }
  .comparison thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
  .comparison tr { margin-bottom: 18px; }
  .comparison td::before { content: attr(data-side); display: block; font-weight: 700; margin-bottom: 8px; color: #285b61; }
  .comparison td + td { border-top: 0; }
}
"""


def _json_text(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
    # Keep ordinary Unicode readable. Display-only control escapes do not change
    # the comparison document or its exact downloadable bytes.
    text = "".join(
        "\\u%04x" % ord(char)
        if 0x7f <= ord(char) <= 0x9f or ord(char) in (0x061c, 0x200e, 0x200f)
        or 0x202a <= ord(char) <= 0x202e or 0x2066 <= ord(char) <= 0x2069
        else char for char in text
    )
    return escape(text, quote=True)


def _pre(value: Any) -> str:
    return "<pre>" + _json_text(value) + "</pre>"


def _table(caption: str, rows: list[tuple[str, Any, Any]]) -> str:
    out = ['<table class="comparison"><caption>', caption,
           '</caption><thead><tr><th scope="col">Field</th><th scope="col">First</th>',
           '<th scope="col">Second</th></tr></thead><tbody>']
    for field, first, second in rows:
        out.extend(['<tr><th scope="row">', _pre(field), '</th>',
                    '<td data-side="First">', _pre(first), '</td>',
                    '<td data-side="Second">', _pre(second), '</td></tr>'])
    out.append('</tbody></table>')
    return "".join(out)


def render_saved_comparison(report: dict[str, Any], native_json: bytes) -> bytes:
    """Render the CLI's admitted report and its exact canonical JSON+LF.

    Admission and serialization belong to compare_inspections. This helper
    performs no file access, ledger reads, dispatch, or output publication.
    """
    first, second = report["first"], report["second"]
    download = base64.b64encode(native_json).decode("ascii")
    out = ['<!doctype html>\n<html lang="en"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width, initial-scale=1">',
           '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
           "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">",
           '<title>Saved inspection comparison</title><style>', _STYLE,
           '</style></head><body><main><header><div class="eyebrow">Fanout · saved data</div>',
           '<h1>Saved inspection comparison</h1>',
           '<p>Read the literal differences between two saved documents. First and second '
           'name the supplied files; their order does not establish chronology.</p>',
           '<p class="notice">These are saved claims. This comparison does not authenticate '
           'their origin or declared plan digest, validate a native plan, resolve uncertainty, '
           'or authorize dispatch, retry or reconciliation.</p>',
           '<a class="download" download="saved-inspection-comparison.json" '
           f'href="data:application/json;base64,{download}">Download exact comparison JSON</a>',
           '<p class="note">The download contains both complete documents, exact input identities '
           'and the original canonical comparison with its final newline. The page is offline '
           'and does not update itself.</p></header>',
           '<section><h2>At a glance</h2><dl class="facts">']
    for label, key in (("Same input bytes", "same_input_bytes"),
                       ("Same saved values", "same_saved_values"),
                       ("Part order changed", "part_order_changed")):
        out.extend(['<div><dt>', label, '</dt><dd>', _json_text(report[key]), '</dd></div>'])
    out.extend(['</dl><h3>Changed part IDs</h3>', _pre(report["changed_part_ids"]),
                '<p class="note">Changed parts follow the first document’s order. A pure '
                'part-order change can have no changed fields.</p></section>',
                '<section><h2>Captured input identities</h2>',
                _table('Raw bytes and declared project relationship', [
                    ('Input bytes', first['input_bytes'], second['input_bytes']),
                    ('Input SHA-256', first['input_sha256'], second['input_sha256']),
                    ('Declared project ID', first['document']['project_id'], second['document']['project_id']),
                    ('Declared plan digest', first['document']['plan_digest'], second['document']['plan_digest']),
                ]), '</section>',
                '<section><h2>Changed fields</h2>',
                '<p>Each side shows its complete JSON envelope. <code>{"present": false}</code> '
                'means absent; a present value of <code>null</code> is different. JSON notation '
                'also preserves booleans, integer/float forms, signed floating zero and array order.</p>',
                '<p class="note">Markup is literal text. Control and directional formatting '
                'characters are shown as JSON escapes; ordinary Unicode stays readable. '
                'The exact download is unchanged by this display treatment.</p>',
                '<h3>Top-level fields</h3>'])
    top = report['top_level_changes']
    if top:
        out.append(_table('Top-level differences', [(r['field'], r['first'], r['second']) for r in top]))
    else:
        out.append('<p>No top-level fields changed.</p>')
    out.append('<h3>Part fields</h3>')
    if report['part_changes']:
        for part in report['part_changes']:
            out.append(_table('Part ' + _json_text(part['part_id']),
                              [(r['field'], r['first'], r['second']) for r in part['fields']]))
    else:
        out.append('<p>No part fields changed.</p>')
    out.extend(['</section><section><h2>Complete saved documents</h2>',
                '<p>These are the complete parsed values, including fields outside the comparison’s '
                'structural admission. Expand either document to read it.</p>',
                '<details><summary>First complete saved document</summary>', _pre(first['document']), '</details>',
                '<details><summary>Second complete saved document</summary>', _pre(second['document']), '</details>',
                '</section></main></body></html>\n'])
    encoded = "".join(out).encode("utf-8")
    if len(encoded) > MAX_HTML_BYTES:
        raise ValueError("HTML report exceeds the 32 MiB consumer limit")
    return encoded
