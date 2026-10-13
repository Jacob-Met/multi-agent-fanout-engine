"""Independent CLI receiving of the saved-inspection HTML projection."""
from __future__ import annotations

import base64
from contextlib import redirect_stderr, redirect_stdout
from html.parser import HTMLParser
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
DOWNLOAD_NAME = "saved-inspection-comparison.json"
PREFIX = "data:application/json;base64,"
BIDI = "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
ORDINARY = "雪 café العربية עברית 👩\u200d💻"


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False,
                       sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def identity(value):
    # Keep JSON's bool/int/float and signed floating-zero distinctions.
    return json.dumps(value, ensure_ascii=False, allow_nan=False,
                      sort_keys=True, separators=(",", ":"))


class Node:
    def __init__(self, tag, attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def text(self):
        return "".join(child if isinstance(child, str) else child.text()
                       for child in self.children)

    def all(self, tag=None):
        for child in self.children:
            if isinstance(child, Node):
                if tag is None or child.tag == tag:
                    yield child
                yield from child.all(tag)


class Page(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self.stack = [self.root]
        self.feed(content.decode("utf-8"))
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img",
                       "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, text):
        self.stack[-1].children.append(text)

    def download(self):
        links = [n for n in self.root.all("a")
                 if n.attrs.get("download") == DOWNLOAD_NAME]
        if len(links) != 1:
            raise AssertionError("expected exactly one native JSON download")
        href = links[0].attrs.get("href", "")
        if not href.startswith(PREFIX):
            raise AssertionError("unexpected download MIME/encoding")
        return base64.b64decode(href[len(PREFIX):], validate=True)

    def pre_values(self):
        values = []
        for node in self.root.all("pre"):
            try:
                values.append(json.loads(node.text()))
            except json.JSONDecodeError:
                pass
        return values

    def field_rows(self):
        rows = []
        for row in self.root.all("tr"):
            cells = [n for n in row.children
                     if isinstance(n, Node) and n.tag in {"th", "td"}]
            if len(cells) != 3:
                continue
            first_blocks = list(cells[1].all("pre"))
            second_blocks = list(cells[2].all("pre"))
            if len(first_blocks) != 1 or len(second_blocks) != 1:
                continue
            try:
                first = json.loads(first_blocks[0].text())
                second = json.loads(second_blocks[0].text())
            except json.JSONDecodeError:
                continue
            if not (isinstance(first, dict) and isinstance(second, dict)
                    and "present" in first and "present" in second):
                continue
            field = cells[0].text()
            try:
                decoded = json.loads(field)
                if isinstance(decoded, str):
                    field = decoded
            except json.JSONDecodeError:
                pass
            rows.append({"field": field, "first": first, "second": second})
        return rows


class InspectionHtmlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        text = ORDINARY + ' <draft> "quoted" & literal\\u202e ' + BIDI + "\x00\x1f\x7f\x85\x9f\t\n"
        self.first_doc = {
            "project_id": 'saved <draft> "project"',
            "plan_digest": "declared-plan",
            "parts": [
                {"id": 'audit <draft>', "state": "outcome_unknown",
                 "text": text, "shape": True, "number": 1, "zero": -0.0,
                 "removed": {"nested": [True, 1, 1.0, None]}},
                {"id": 'summary "\n雪', "state": "queued"},
                {"id": "stable", "state": "completed", "literal": ORDINARY},
            ],
            "state_counts": {"completed": 1, "outcome_unknown": 1, "queued": 1},
            "removed_top": {"all": ["kept literally", None]},
            'field "<draft>"\nname': "first",
        }
        self.second_doc = json.loads(json_bytes(self.first_doc))
        first = self.second_doc["parts"][0]
        first.update(state="completed", shape=1, number=1.0, zero=0.0, nullable=None)
        del first["removed"]
        self.second_doc["parts"][1]["state"] = "completed"
        self.second_doc["state_counts"] = {"completed": 3, "outcome_unknown": 0, "queued": 0}
        del self.second_doc["removed_top"]
        self.second_doc["added_top"] = None
        self.second_doc['field "<draft>"\nname'] = "second"
        self.first = self.work / "first.json"
        self.second = self.work / "second.json"
        self.first.write_bytes(json_bytes(self.first_doc))
        self.second.write_bytes(json_bytes(self.second_doc))
        self.input_bytes = (self.first.read_bytes(), self.second.read_bytes())

    def command(self, *extra):
        args = [sys.executable, "-B"]
        if sys.flags.optimize:
            args.append("-O")
        args += ["-m", "fanout_engine.compare_inspections",
                 "--first", str(self.first), "--second", str(self.second), *extra]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run(args, cwd=ROOT, env=env, capture_output=True,
                              timeout=30, check=False)

    def html(self, *extra):
        result = self.command("--format", "html", *extra)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertEqual(result.stderr, b"")
        self.assertTrue(result.stdout.endswith(b"\n"))
        return result.stdout, Page(result.stdout)

    def assert_inputs_unchanged(self):
        self.assertEqual((self.first.read_bytes(), self.second.read_bytes()), self.input_bytes)

    def assert_inert(self, page):
        forbidden = {"script", "iframe", "object", "embed", "form", "base", "link",
                     "img", "video", "audio", "svg", "math", "input"}
        for node in page.root.all():
            self.assertNotIn(node.tag, forbidden)
            for key, value in node.attrs.items():
                self.assertFalse(key.lower().startswith("on"))
                self.assertNotIn(key.lower(), {"src", "srcset"})
                if key.lower() == "href":
                    self.assertTrue(value.startswith(PREFIX) or value.startswith("#"), value)
            if node.tag == "style":
                self.assertNotIn("@import", node.text().lower())
                self.assertNotIn("url(", node.text().lower())

    def test_default_json_and_html_are_deterministic_and_download_exact(self):
        native = self.command()
        explicit = self.command("--format", "json")
        self.assertEqual((native.returncode, explicit.returncode), (0, 0))
        self.assertEqual(native.stderr + explicit.stderr, b"")
        self.assertEqual(native.stdout, explicit.stdout)
        first, page = self.html()
        second, _ = self.html()
        self.assertEqual(first, second)
        self.assertEqual(page.download(), native.stdout)
        self.assertTrue(native.stdout.endswith(b"\n"))
        output = self.work / "comparison.html"
        file_result = self.command("--format", "html", "--output", str(output))
        self.assertEqual(file_result.returncode, 0, file_result.stderr)
        self.assertEqual(file_result.stdout + file_result.stderr, b"")
        self.assertEqual(output.read_bytes(), first)
        self.assert_inputs_unchanged()

    def test_complete_documents_presence_and_native_row_order_are_visible(self):
        _, page = self.html()
        report = json.loads(page.download())
        values = [identity(value) for value in page.pre_values()]
        self.assertIn(identity(self.first_doc), values)
        self.assertIn(identity(self.second_doc), values)
        expected = list(report["top_level_changes"])
        for part in report["part_changes"]:
            expected.extend(part["fields"])
        self.assertEqual(identity(page.field_rows()), identity(expected))
        self.assertIn(identity({"present": False}), values)
        self.assertIn(identity({"present": True, "value": None}), values)
        self.assertEqual(report["changed_part_ids"], ['audit <draft>', 'summary "\n雪'])
        text = page.root.text()
        for side in ("first", "second"):
            self.assertIn(report[side]["input_sha256"], text)
            self.assertIn(str(report[side]["input_bytes"]), text)
        self.assertEqual([n.text().strip() for n in page.root.all("h1")],
                         ["Saved inspection comparison"])
        self.assertGreaterEqual(len(list(page.root.all("h2"))), 4)
        tables = list(page.root.all("table"))
        self.assertTrue(tables)
        for table in tables:
            self.assertTrue(list(table.all("caption")))
            headers = [n.text().strip() for n in table.all("th")]
            self.assertIn("First", headers)
            self.assertIn("Second", headers)
        self.assert_inputs_unchanged()

    def test_authored_unicode_controls_and_markup_stay_literal_and_inert(self):
        _, page = self.html()
        self.assert_inert(page)
        report = json.loads(page.download())
        self.assertEqual(identity(report["first"]["document"]), identity(self.first_doc))
        text = page.root.text()
        self.assertIn(ORDINARY, text)
        self.assertIn("<draft>", text)
        for char in BIDI + "\x00\x1f\x7f\x85\x9f":
            self.assertNotIn(char, text)
        for char in BIDI + "\x7f\x85\x9f":
            self.assertIn("\\u" + format(ord(char), "04x"), text.lower())
        self.assertIn("\\\\u202e", text)  # authored literal slash-u is still distinct
        ids = [node.attrs["id"] for node in page.root.all() if "id" in node.attrs]
        self.assertEqual(len(ids), len(set(ids)))
        for authored in (self.first_doc["project_id"], *(p["id"] for p in self.first_doc["parts"])):
            self.assertNotIn(authored, ids)
        self.assert_inputs_unchanged()

    def test_identical_formatting_only_and_part_order_only_are_explicit(self):
        cases = [
            ("identical", self.first.read_bytes(), True, True, False),
            ("formatting", json.dumps(self.first_doc, ensure_ascii=False, indent=3).encode("utf-8"),
             False, True, False),
        ]
        reordered = json.loads(self.first.read_bytes())
        reordered["parts"] = list(reversed(reordered["parts"]))
        cases.append(("order", json_bytes(reordered), False, False, True))
        for name, data, same_bytes, same_values, order in cases:
            with self.subTest(name=name):
                self.second.write_bytes(data)
                _, page = self.html()
                report = json.loads(page.download())
                self.assertEqual((report["same_input_bytes"], report["same_saved_values"],
                                  report["part_order_changed"]), (same_bytes, same_values, order))
                self.assertEqual(report["top_level_changes"], [])
                self.assertEqual(report["part_changes"], [])
                self.assertEqual(page.field_rows(), [])
                self.assertIn(identity(json.loads(data)), [identity(v) for v in page.pre_values()])
        self.assertEqual(self.first.read_bytes(), self.input_bytes[0])

    def test_invalid_input_and_format_refuse_before_output(self):
        for name, data, format_name in [
            ("malformed", b'{"parts":', "html"),
            ("relationship", json_bytes(dict(self.second_doc, project_id="different")), "html"),
            ("format", self.input_bytes[1], "unknown-format"),
        ]:
            with self.subTest(name=name):
                self.second.write_bytes(data)
                output = self.work / (name + ".html")
                result = self.command("--format", format_name, "--output", str(output))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertTrue(result.stderr)
                self.assertFalse(output.exists())
                self.assertEqual(self.second.read_bytes(), data)
        self.assertEqual(self.first.read_bytes(), self.input_bytes[0])

    def test_html_publication_preserves_occupied_and_input_destinations(self):
        occupied = self.work / "occupied.html"
        occupied.write_bytes(b"existing report\n")
        for output in (occupied, self.first, self.second):
            with self.subTest(output=output.name):
                before = {p.name: p.read_bytes() for p in self.work.iterdir()}
                result = self.command("--format", "html", "--output", str(output))
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertTrue(result.stderr)
                self.assertEqual({p.name: p.read_bytes() for p in self.work.iterdir()}, before)
        self.assert_inputs_unchanged()

    def test_html_limit_is_checked_before_publication_without_changing_json(self):
        from fanout_engine import compare_inspections as cli
        from fanout_engine import compare_inspections_html as renderer
        output = self.work / "bounded.html"
        args = ["--first", str(self.first), "--second", str(self.second)]
        with mock.patch.object(renderer, "MAX_HTML_BYTES", 1):
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = cli.main(args + ["--format", "html", "--output", str(output)])
            self.assertEqual(result, 2)
            self.assertTrue(stderr.getvalue())
            self.assertFalse(output.exists())
            native_file = self.work / "still-native.json"
            self.assertEqual(cli.main(args + ["--format", "json", "--output", str(native_file)]), 0)
            self.assertEqual(json.loads(native_file.read_bytes())["schema"],
                             "fanout.saved-inspection-comparison/1")
        self.assert_inputs_unchanged()

    def test_imported_html_file_works_with_unavailable_stdout(self):
        from fanout_engine import compare_inspections as cli
        output = self.work / "without-stdout.html"
        args = ["--first", str(self.first), "--second", str(self.second),
                "--format", "html", "--output", str(output)]
        stderr = io.StringIO()
        with redirect_stdout(None), redirect_stderr(stderr):
            self.assertEqual(cli.main(args), 0)
            self.assertIsNone(sys.stdout)
        self.assertEqual(stderr.getvalue(), "")
        page = Page(output.read_bytes())
        self.assertEqual(json.loads(page.download())["schema"],
                         "fanout.saved-inspection-comparison/1")
        self.assert_inputs_unchanged()


if __name__ == "__main__":
    unittest.main()
