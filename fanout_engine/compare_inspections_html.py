"""Static HTML projection of an admitted saved-inspection comparison."""
from __future__ import annotations

import base64
from html import escape
import json
from typing import Any

MAX_HTML_BYTES = 32 * 1024 * 1024
_BIDI_CONTROLS = frozenset((0x061C, 0x200E, 0x200F, *range(0x202A, 0x202F),
                            *range(0x2066, 0x206A)))

_STYLE = """
:root { color-scheme: light; font-family: system-ui, sans-serif; color: #183038; background: #f3f6f3; }
* { box-sizing: border-box; }
body { margin: 0; }
main { max-width: 1120px; margin: auto; padding: 36px 24px 56px; }
h1 { margin: 0 0 16px; font-size: clamp(1.8rem, 4vw, 2.8rem); line-height: 1.15; }
h2 { margin: 0 0 18px; font-size: 1.4rem; }
h3 { font-size: 1.1rem; }
p, li, dt, dd, summary { line-height: 1.65; }
header > p { max-width: 80ch; }
section { margin-top: 24px; padding: 24px; background: white; border: 1px solid #ccd9d2; border-radius: 12px; }
a { color: #165e4c; text-underline-offset: 3px; overflow-wrap: anywhere; }
a:focus-visible, summary:focus-visible { outline: 3px solid #985c00; outline-offset: 4px; }
.download { display: inline-block; padding: 12px 16px; border: 1px solid #165e4c; border-radius: 6px; font-weight: 650; }
.note { color: #4a6168; font-size: .9rem; }
dl { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px 24px; }
dt { font-weight: 650; }
dd { margin: 0; }
table { width: 100%; table-layout: fixed; border-collapse: collapse; margin-top: 20px; }
caption { text-align: left; font-weight: 650; padding-bottom: 10px; overflow-wrap: anywhere; }
th, td { border: 1px solid #ccd9d2; padding: 12px; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
th { background: #eff5f0; }
pre, code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .85rem; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; unicode-bidi: plaintext; }
pre { margin: 0; }
.side-label { display: none; font-size: .8rem; font-weight: 650; margin-bottom: 6px; }
details { margin-top: 18px; }
summary { cursor: pointer; font-weight: 650; }
.document { padding: 18px; margin-top: 12px; background: #f6f8f5; border: 1px solid #ccd9d2; border-radius: 6px; }
@media (max-width: 600px) {
  main { padding: 24px 12px 40px; }
  section { padding: 18px 12px; }
  dl { gap: 10px 12px; }
  table, tbody, tr, th, td { display: block; width: 100%; }
  caption { display: block; width: 100%; }
  thead { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
  tr { margin-bottom: 16px; }
  th, td { border-bottom: 0; }
  td:last-child { border-bottom: 1px solid #ccd9d2; }
  .side-label { display: block; }
}
"""


def _value(value: Any, *, pretty: bool = False) -> str:
    text = json.dumps(value, ensure_ascii=False, allow_nan=False,
                      indent=2 if pretty else None,
                      separators=None if pretty else (",", ":"))
    # Transform actual formatting controls after JSON encoding. Authored
    # backslash-u text is already doubled and stays distinguishable.
    text = "".join(f"\\u{ord(char):04x}"
                   if 0x7F <= ord(char) <= 0x9F or ord(char) in _BIDI_CONTROLS
                   else char for char in text)
    return escape(text, quote=True)


def _pre(value: Any, identity: str, *, pretty: bool = False) -> str:
    # Every identity is supplied below from fixed strings and numeric indexes.
    return f'<pre id="{identity}">{_value(value, pretty=pretty)}</pre>'


def _row(field: Any, first: Any, second: Any, identity: str) -> str:
    return ('<tr><th scope="row">' + _pre(field, identity + "-field") +
            '</th><td><span class="side-label" aria-hidden="true">First</span>' +
            _pre(first, identity + "-first") +
            '</td><td><span class="side-label" aria-hidden="true">Second</span>' +
            _pre(second, identity + "-second") + "</td></tr>")


def _table(caption: str, rows: list[str]) -> str:
    return ("<table><caption>" + caption +
            '</caption><thead><tr><th scope="col">Field</th>'
            '<th scope="col">First</th><th scope="col">Second</th>'
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


def render_comparison(report: dict[str, Any], native_json: bytes) -> bytes:
    """Render the CLI's admitted result with its exact serialized JSON.

    Admission and serialization belong to compare_inspections. This helper
    does not read files, compare inputs, open a Ledger or publish output.
    """
    first, second = report["first"], report["second"]
    download = base64.b64encode(native_json).decode("ascii")
    out = [
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">",
        "<title>Saved inspection comparison</title>",
        f"<style>{_STYLE}</style></head><body><main>",
        "<header><h1>Saved inspection comparison</h1>",
        "<p>Read the literal differences between two saved observations. "
        "First and Second follow the supplied input order; these labels do not "
        "establish chronology or verify external work.</p>",
        '<a class="download" download="saved-inspection-comparison.json" '
        f'href="data:application/json;base64,{download}">Download exact comparison JSON</a>',
        '<p class="note">The download preserves the complete native JSON report and its final newline. '
        "This static page opens no ledger, runs no work and supplies no retry authorization.</p></header>",
        '<section aria-labelledby="summary-heading"><h2 id="summary-heading">Saved differences</h2><dl>',
    ]
    for label, key in (
        ("Identical input bytes", "same_input_bytes"),
        ("Equal saved values", "same_saved_values"),
        ("Part order changed", "part_order_changed"),
    ):
        out.append(f"<dt>{label}</dt><dd>" + _pre(report[key], key) + "</dd>")
    out.extend([
        "</dl><h3>Parts with changed fields</h3>",
        _pre(report["changed_part_ids"], "changed-part-ids"),
        '<p class="note">Changed parts follow First document order. Changed fields are sorted '
        "by name. A part-order change alone does not create field-change rows.</p></section>",
        '<section aria-labelledby="identity-heading"><h2 id="identity-heading">Input identities</h2>',
        _table("Declared identity and exact saved input bytes", [
            _row("Project ID", first["document"]["project_id"], second["document"]["project_id"], "identity-0"),
            _row("Declared plan digest", first["document"]["plan_digest"], second["document"]["plan_digest"], "identity-1"),
            _row("Input bytes", first["input_bytes"], second["input_bytes"], "identity-2"),
            _row("Input SHA-256", first["input_sha256"], second["input_sha256"], "identity-3"),
        ]),
        '<p class="note">Shared declarations permit this comparison. They do not authenticate '
        "either observation or prove it describes the current state.</p></section>",
        '<section aria-labelledby="changes-heading"><h2 id="changes-heading">Changed fields</h2>',
        '<p class="note">Each side is a complete JSON object: <code>{"present":false}</code> '
        'means absent; <code>{"present":true,"value":null}</code> means present with a null value. '
        "Nested values remain complete. No timestamp sorting or subtraction is performed.</p>",
    ])
    top = report["top_level_changes"]
    if top:
        out.append(_table("Top-level fields", [
            _row(row["field"], row["first"], row["second"], f"top-{index}")
            for index, row in enumerate(top)
        ]))
    else:
        out.append("<p>No top-level fields changed.</p>")
    for part_index, part in enumerate(report["part_changes"]):
        out.append(_table("Part " + _value(part["part_id"]), [
            _row(row["field"], row["first"], row["second"], f"part-{part_index}-{field_index}")
            for field_index, row in enumerate(part["fields"])
        ]))
    if not report["part_changes"]:
        out.append("<p>No part fields changed.</p>")
    out.extend([
        "</section>",
        '<section aria-labelledby="documents-heading"><h2 id="documents-heading">Complete saved documents</h2>',
        '<p class="note">All displayed data uses literal JSON notation. Control and bidi formatting '
        "characters appear as escapes; ordinary Unicode letters and emoji joiners are preserved. "
        "Literal backslash sequences retain JSON escaping. The downloaded native report is unchanged.</p>",
    ])
    for label, side in (("First", first), ("Second", second)):
        out.extend([
            "<details><summary>Complete " + label + " document</summary>",
            '<div class="document">',
            _pre(side["document"], label.lower() + "-document", pretty=True),
            "</div></details>",
        ])
    out.append("</section></main></body></html>\n")
    encoded = "".join(out).encode("utf-8")
    if len(encoded) > MAX_HTML_BYTES:
        raise ValueError("HTML report exceeds the 32 MiB consumer limit")
    return encoded
