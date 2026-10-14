"""Self-contained HTML rendering of an admitted native plan comparison."""
from __future__ import annotations

import base64
from html import escape
import json
from typing import Any

MAX_HTML_BYTES = 32 * 1024 * 1024

_STYLE = """
:root { color-scheme: light; font-family: system-ui, sans-serif; color: #182334; background: #f2f5f8; }
* { box-sizing: border-box; }
body { margin: 0; }
main { max-width: 1120px; margin: 0 auto; padding: 32px 24px 56px; }
h1 { margin: 0 0 12px; font-size: 2rem; line-height: 1.2; }
h2 { margin: 0 0 18px; font-size: 1.35rem; }
h3 { margin: 24px 0 12px; font-size: 1.1rem; }
p, li, dt, dd { line-height: 1.6; }
section { margin-top: 24px; padding: 24px; border: 1px solid #cbd5e1; border-radius: 12px; background: white; }
a { color: #174ea6; text-decoration-thickness: 2px; text-underline-offset: 3px; overflow-wrap: anywhere; }
a:focus-visible { outline: 3px solid #985300; outline-offset: 5px; }
.download { display: inline-block; padding: 12px 16px; border: 1px solid #174ea6; border-radius: 6px; font-weight: 650; }
dl { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 10px 24px; }
dt { font-weight: 650; }
dd { margin: 0; }
table { width: 100%; table-layout: fixed; border-collapse: collapse; margin-top: 12px; }
caption { text-align: left; font-weight: 650; margin-bottom: 10px; }
th, td { padding: 12px; border: 1px solid #cbd5e1; vertical-align: top; text-align: left; overflow-wrap: anywhere; }
th { background: #edf2f7; font-size: .9rem; }
pre, code { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: .85rem; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; word-break: normal; }
pre { margin: 0; }
.plan { padding: 16px; border: 1px solid #cbd5e1; border-radius: 6px; background: #f8fafc; }
.note { color: #455468; }
@media (max-width: 600px) {
  main { padding: 24px 12px 40px; }
  section { padding: 16px 12px; }
  h1 { font-size: 1.65rem; }
  th, td { padding: 8px 6px; }
  dl { gap: 10px 12px; }
}
"""


def _value(value: Any, *, pretty: bool = False) -> str:
    # JSON notation makes control characters, quotes and whitespace explicit;
    # HTML escaping then keeps every authored value outside the markup grammar.
    text = json.dumps(value, ensure_ascii=False, allow_nan=False,
                      indent=2 if pretty else None,
                      separators=None if pretty else (",", ":"))
    return escape(text, quote=True)


def _pre(value: Any, identity: str | None = None, *, pretty: bool = False) -> str:
    attribute = f' id="{identity}"' if identity is not None else ""
    return f"<pre{attribute}>{_value(value, pretty=pretty)}</pre>"


def render_comparison(report: dict[str, Any], native_json: bytes) -> bytes:
    """Render the CLI's admitted report and its exact canonical JSON bytes.

    The comparator owns admission and serialization. This presentation helper
    does not read files, create a Plan, open a Ledger or publish any output.
    """
    before = report["before"]
    after = report["after"]
    before_parts = {part["id"]: part for part in before["plan"]["parts"]}
    after_parts = {part["id"]: part for part in after["plan"]["parts"]}
    download = base64.b64encode(native_json).decode("ascii")
    out = [
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">",
        "<title>Plan draft comparison</title>",
        f"<style>{_STYLE}</style></head><body><main>",
        "<header><h1>Plan draft comparison</h1>",
        "<p>Review the directional changes from the before draft to the after draft. "
        "This page contains authored plans and native identities; it does not describe "
        "stored task states, authorize a submission or reuse a key.</p>",
        '<a class="download" download="plan-comparison.json" '
        f'href="data:application/json;base64,{download}">Download exact comparison JSON</a>',
        '<p class="note">The download is the complete native CLI report, including '
        "captured input hashes and its final newline. Values below use JSON notation "
        "so quotes, control characters and whitespace remain explicit.</p></header>",
        '<section aria-labelledby="summary-heading"><h2 id="summary-heading">Summary</h2><dl>',
    ]
    for label, key, identity in (
        ("Same native plan", "same_plan", "same-plan"),
        ("Project ID changed", "project_id_changed", "project-id-changed"),
        ("Complete part order changed", "part_order_changed", "part-order-changed"),
    ):
        out.append(f'<dt>{label}</dt><dd id="{identity}">{_value(report[key])}</dd>')
    out.extend([
        "</dl><h3>Added parts</h3>", _pre(report["added_part_ids"], "added-part-ids"),
        "<h3>Removed parts</h3>", _pre(report["removed_part_ids"], "removed-part-ids"),
        '<p class="note">Added IDs follow after declaration order; removed IDs follow '
        "before declaration order. An addition or removal also changes the complete part order.</p></section>",
        '<section id="identity" aria-labelledby="identity-heading">'
        '<h2 id="identity-heading">Captured identities</h2>',
        "<table><caption>Native identity and exact CLI input bytes</caption>"
        '<thead><tr><th scope="col">Field</th><th scope="col">Before</th>'
        '<th scope="col">After</th></tr></thead><tbody>',
    ])
    for label, old, new in (
        ("Project ID", before["plan"]["project"], after["plan"]["project"]),
        ("Native plan digest", before["plan_digest"], after["plan_digest"]),
        ("Input SHA-256", report["input_sha256"]["before"], report["input_sha256"]["after"]),
    ):
        out.append(f'<tr><th scope="row">{label}</th><td>{_pre(old)}</td><td>{_pre(new)}</td></tr>')
    out.extend(["</tbody></table></section>",
                '<section id="changes" aria-labelledby="changes-heading">'
                '<h2 id="changes-heading">Changed retained fields</h2>'])
    if not report["changed_parts"]:
        out.append("<p>No retained part fields changed.</p>")
    for index, change in enumerate(report["changed_parts"]):
        part_id = change["part_id"]
        out.append("<table><caption>Part " + _value(part_id) +
                   '</caption><thead><tr><th scope="col">Field</th>'
                   '<th scope="col">Before</th><th scope="col">After</th></tr></thead><tbody>')
        for field in change["fields"]:
            out.append(f'<tr><th scope="row">{escape(field)}</th><td>' +
                       _pre(before_parts[part_id][field], f"change-{index}-{field}-before") +
                       "</td><td>" +
                       _pre(after_parts[part_id][field], f"change-{index}-{field}-after") +
                       "</td></tr>")
        out.append("</tbody></table>")
    out.extend([
        "</section>",
        '<section aria-labelledby="before-heading"><h2 id="before-heading">Complete before plan</h2>',
        '<div class="plan">', _pre(before["plan"], "before-plan-json", pretty=True), "</div></section>",
        '<section aria-labelledby="after-heading"><h2 id="after-heading">Complete after plan</h2>',
        '<div class="plan">', _pre(after["plan"], "after-plan-json", pretty=True), "</div></section>",
        '<section aria-labelledby="keys-heading"><h2 id="keys-heading">Native idempotency keys</h2>',
        '<p class="note">Keys include the complete native plan digest. An unchanged part '
        "can receive a changed key when another part changes. A missing side is null; "
        "this comparison supplies no permission to reuse a key.</p>",
        "<table><caption>All part keys, in after order followed by removed parts</caption>",
        '<thead><tr><th scope="col">Part ID</th><th scope="col">Before key</th>'
        '<th scope="col">After key</th><th scope="col">Changed</th></tr></thead><tbody>',
    ])
    for index, row in enumerate(report["idempotency_keys"]):
        out.append("<tr><th scope=\"row\">" + _pre(row["part_id"], f"key-{index}-part") +
                   "</th><td>" + _pre(row["before"], f"key-{index}-before") +
                   "</td><td>" + _pre(row["after"], f"key-{index}-after") +
                   "</td><td>" + _pre(row["changed"], f"key-{index}-changed") + "</td></tr>")
    out.extend(["</tbody></table></section></main></body></html>\n"])
    encoded = "".join(out).encode("utf-8")
    if len(encoded) > MAX_HTML_BYTES:
        raise ValueError("HTML report exceeds the 32 MiB consumer limit")
    return encoded
