"""Actual saved-report CLI and passive HTML presentation boundaries."""
from __future__ import annotations

import base64
import copy
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fanout_engine.compare_inspections import main

ROOT = Path(__file__).resolve().parents[1]


def raw(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


class Page(HTMLParser):
    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.attrs = []
        self.pres = []
        self.downloads = []
        self.visible = []
        self.current_pre = None
        self.feed(body.decode("utf-8"))

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend(attrs)
        attr = dict(attrs)
        if tag == "pre":
            self.current_pre = []
        if tag == "a" and "download" in attr:
            self.downloads.append(attr)

    def handle_data(self, data):
        self.visible.append(data)
        if self.current_pre is not None:
            self.current_pre.append(data)

    def handle_endtag(self, tag):
        if tag == "pre":
            self.pres.append("".join(self.current_pre))
            self.current_pre = None

    def downloaded(self):
        if len(self.downloads) != 1:
            raise ValueError("one exact native download required")
        prefix = "data:application/json;base64,"
        href = self.downloads[0]["href"]
        if not href.startswith(prefix):
            raise ValueError("unexpected download type")
        return base64.b64decode(href[len(prefix):], validate=True)


class SavedInspectionHTMLTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.first = self.directory / "first.json"
        self.second = self.directory / "second.json"
        self.left = {"project_id": "saved project", "plan_digest": "declared only", "parts": [
            {"id": "audit", "state": "outcome_unknown", "absent_later": None, "flag": False,
             "number": 1, "zero": -0.0, "ordered": [1, 2],
             "text": "<script>literal</script> & 雪 مرحبا 👩‍💻\n\u202e\u007f\u0085"},
            {"id": "publish", "state": "queued"}], "unknown_field": {"a": True}}
        self.right = copy.deepcopy(self.left)
        part = self.right["parts"][0]
        part.update({"flag": 0, "number": 1.0, "zero": 0.0, "ordered": [2, 1], "present_null": None})
        del part["absent_later"]
        self.right["parts"].reverse()
        self.first.write_bytes(raw(self.left))
        self.second.write_bytes(raw(self.right))

    def cli(self, *args):
        return subprocess.run([sys.executable, "-B", *(["-O"] if sys.flags.optimize else []),
                               "-m", "fanout_engine.compare_inspections", "--first", str(self.first),
                               "--second", str(self.second), *map(str, args)],
                              cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)

    def successful(self, *args):
        result = self.cli(*args)
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        return result.stdout

    def test_default_explicit_json_and_html_download_stdout_file_identity(self):
        before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in (self.first, self.second)]
        native = self.successful()
        self.assertEqual(self.successful("--format", "json"), native)
        html = self.successful("--format", "html")
        self.assertEqual(self.successful("--format", "html"), html)
        page = Page(html)
        self.assertEqual(page.downloaded(), native)
        self.assertTrue(native.endswith(b"\n"))
        self.assertEqual(page.downloads[0]["download"], "saved-inspection-comparison.json")
        destination = self.directory / "review.html"
        self.assertEqual(self.successful("--format", "html", "--output", destination), b"")
        self.assertEqual(destination.read_bytes(), html)
        self.assertEqual([(p.read_bytes(), p.stat().st_mtime_ns) for p in (self.first, self.second)], before)

    def test_complete_typed_envelopes_documents_and_order_preserved(self):
        page = Page(self.successful("--format", "html"))
        report = json.loads(page.downloaded())
        parsed = [json.loads(value) for value in page.pres]
        # Canonical encoded values avoid Python's bool/int and signed-zero aliases.
        values = [raw(value) for value in parsed]
        for field in report["part_changes"][0]["fields"]:
            self.assertIn(raw(field["field"]), values)
            self.assertIn(raw(field["first"]), values)
            self.assertIn(raw(field["second"]), values)
        self.assertIn(raw({"present": False}), values)
        self.assertIn(raw({"present": True, "value": None}), values)
        self.assertIn(raw({"present": True, "value": False}), values)
        self.assertIn(raw({"present": True, "value": 0}), values)
        self.assertIn(raw({"present": True, "value": 1}), values)
        self.assertIn(raw({"present": True, "value": 1.0}), values)
        self.assertIn(raw({"present": True, "value": -0.0}), values)
        self.assertIn(raw({"present": True, "value": 0.0}), values)
        self.assertIn(raw(self.left), values)
        self.assertIn(raw(self.right), values)
        for side in ("first", "second"):
            self.assertIn(raw(report[side]["input_sha256"]), values)
            self.assertIn(raw(report[side]["input_bytes"]), values)

    def test_literal_escaping_passive_page_and_readable_unicode(self):
        html = self.successful("--format", "html")
        page = Page(html)
        self.assertFalse(set(page.tags) & {"script", "iframe", "object", "form", "img", "link", "svg"})
        self.assertFalse(any(name.startswith("on") for name, _ in page.attrs))
        self.assertEqual([value for name, value in page.attrs if name in ("src", "href")],
                         [page.downloads[0]["href"]])
        text = "".join(page.visible)
        self.assertIn("<script>literal</script>", text)
        self.assertIn("雪 مرحبا 👩‍💻", text)
        self.assertIn("\\u202e", text)
        self.assertIn("\\u007f", text)
        self.assertIn("\\u0085", text)
        self.assertNotIn("\u202e", text)
        self.assertIn("does not establish chronology", text)
        self.assertIn("retry or reconciliation", text)
        self.assertEqual(json.loads(page.downloaded())["first"]["document"], self.left)

    def test_order_only_identical_and_empty_parts_have_distinct_summary(self):
        ordered = copy.deepcopy(self.left)
        ordered["parts"].reverse()
        self.second.write_bytes(raw(ordered))
        page = Page(self.successful("--format", "html"))
        report = json.loads(page.downloaded())
        self.assertIs(report["part_order_changed"], True)
        self.assertIs(report["same_saved_values"], False)
        self.assertEqual(report["part_changes"], [])
        self.assertIn("No part fields changed.", "".join(page.visible))
        self.second.write_bytes(self.first.read_bytes())
        identical = json.loads(Page(self.successful("--format", "html")).downloaded())
        self.assertIs(identical["same_input_bytes"], True)
        self.assertIs(identical["same_saved_values"], True)
        self.assertIs(identical["part_order_changed"], False)
        empty = {"project_id": "p", "plan_digest": "d", "parts": []}
        self.first.write_bytes(raw(empty)); self.second.write_bytes(raw(empty))
        self.assertEqual(json.loads(Page(self.successful("--format", "html")).downloaded())["changed_part_ids"], [])

    def test_existing_input_dangling_and_missing_parent_outputs_refused(self):
        occupied = self.directory / "occupied.html"
        occupied.write_bytes(b"keep exact\n")
        before = {str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in (self.first, self.second, occupied)}
        for destination in (occupied, self.first, self.second, self.directory / "missing" / "report.html"):
            with self.subTest(destination=destination):
                child = self.cli("--format", "html", "--output", destination)
                self.assertEqual(child.returncode, 1)
                self.assertEqual(child.stdout, b"")
        self.assertEqual({str(p): (p.read_bytes(), p.stat().st_mtime_ns) for p in (self.first, self.second, occupied)}, before)
        self.assertFalse((self.directory / "missing").exists())
        if hasattr(Path, "symlink_to"):
            dangling = self.directory / "dangling.html"
            try:
                dangling.symlink_to(self.directory / "absent-target")
            except (OSError, NotImplementedError):
                return  # The platform may not grant symlink creation.
            child = self.cli("--format", "html", "--output", dangling)
            self.assertEqual(child.returncode, 1)
            self.assertTrue(dangling.is_symlink())
            self.assertFalse((self.directory / "absent-target").exists())

    def test_native_admission_and_html_size_bound_precede_publication(self):
        output = self.directory / "invalid.html"
        self.second.write_bytes(b'{"project_id": "wrong", "plan_digest": "other", "parts": []}\n')
        child = self.cli("--format", "html", "--output", output)
        self.assertEqual((child.returncode, child.stdout), (2, b""))
        self.assertFalse(output.exists())
        self.second.write_bytes(raw(self.right))
        args = ["--first", str(self.first), "--second", str(self.second), "--format", "html", "--output", str(output)]
        with patch("fanout_engine.compare_inspections_html.MAX_HTML_BYTES", 64), patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(main(args), 2)
            self.assertIn("HTML report exceeds", stderr.getvalue())
        self.assertFalse(output.exists())
        self.assertFalse(any(p.name.startswith(".") for p in self.directory.iterdir()))

    def test_html_stdout_failure_uses_existing_output_exit(self):
        args = ["--first", str(self.first), "--second", str(self.second), "--format", "html"]
        with patch("fanout_engine.compare_inspections._write_stdout", side_effect=OSError("owned broken output")), patch("sys.stderr", new_callable=io.StringIO) as stderr:
            self.assertEqual(main(args), 1)
            self.assertIn("cannot write report", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
