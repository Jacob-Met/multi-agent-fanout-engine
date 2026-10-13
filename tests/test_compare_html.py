"""Receive complete offline plan comparisons through the real CLI."""
from __future__ import annotations

import base64
from html.parser import HTMLParser
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(os.environ.get("FANOUT_SOURCE_ROOT", Path(__file__).resolve().parents[1]))


class Page(HTMLParser):
    def __init__(self, data):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.links = []
        self.ids = {}
        self.stack = []
        self.feed(data.decode("utf-8"))

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if tag == "a":
            self.links.append(attrs)
        if "id" in attrs:
            self.ids[attrs["id"]] = ""
        if tag not in {"meta", "br", "hr", "link", "input", "img"}:
            self.stack.append((tag, attrs.get("id")))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        for _, identity in self.stack:
            if identity:
                self.ids[identity] += data

    def download(self):
        matches = [a for a in self.links if a.get("download") == "plan-comparison.json"]
        if len(matches) != 1:
            raise AssertionError(matches)
        prefix = "data:application/json;base64,"
        if not matches[0]["href"].startswith(prefix):
            raise AssertionError(matches[0])
        return base64.b64decode(matches[0]["href"][len(prefix):], validate=True)


class ComparisonHtmlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.before = self.work / "before #% café.json"
        self.after = self.work / "after 東京.json"
        self.old = {
            "project": "review",
            "parts": [
                {"id": "gather", "instruction": "Collect café references — 東京 🌿."},
                {"id": "context", "instruction": "Keep context.\n\tKeep a tab."},
                {"id": "retire", "instruction": "Old task."},
                {"id": "draft", "instruction": "Old text.\r\nSecond line.",
                 "depends_on": ["gather", "context"], "tags": ["old"]},
            ],
        }
        self.new = {
            "project": "review",
            "parts": [
                {"id": "draft",
                 "instruction": "New <reader> & \"quoted\" text.\n"
                    "</pre><script>window.CANARY = true</script>\x00\r\t🌿",
                 "depends_on": ["context", "gather"], "tags": ["new", "new"]},
                self.old["parts"][0], self.old["parts"][1],
                {"id": "review", "instruction": "Review.", "depends_on": ["draft"]},
            ],
        }
        self.write(self.before, self.old)
        self.write(self.after, self.new)
        self.original_bytes = (self.before.read_bytes(), self.after.read_bytes())

    @staticmethod
    def write(path, value):
        path.write_bytes((json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8"))

    def run_cli(self, *extra, stdout=subprocess.PIPE):
        return subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.compare",
             "--before", str(self.before), "--after", str(self.after), *extra],
            cwd=ROOT, stdout=stdout, stderr=subprocess.PIPE, timeout=20,
        )

    def native(self):
        result = self.run_cli()
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        return result.stdout

    def html(self, *extra):
        result = self.run_cli("--format", "html", *extra)
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        return result.stdout

    def test_default_json_native_control(self):
        report = json.loads(self.native())
        self.assertEqual(report["added_part_ids"], ["review"])
        self.assertEqual(report["removed_part_ids"], ["retire"])
        self.assertEqual(report["changed_parts"], [
            {"part_id": "draft", "fields": ["instruction", "depends_on", "tags"]}])
        self.assertEqual(report["input_sha256"], {
            "before": hashlib.sha256(self.original_bytes[0]).hexdigest(),
            "after": hashlib.sha256(self.original_bytes[1]).hexdigest(),
        })

    def test_explicit_json_is_default_byte_for_byte(self):
        explicit = self.run_cli("--format", "json")
        self.assertEqual((explicit.returncode, explicit.stderr), (0, b""))
        self.assertEqual(explicit.stdout, self.native())

    def test_html_download_is_exact_native_report(self):
        page = Page(self.html())
        self.assertEqual(page.download(), self.native())
        self.assertTrue(page.download().endswith(b"\n"))

    def test_full_plans_edits_keys_and_input_hashes_are_visible(self):
        report = json.loads(self.native())
        page = Page(self.html())
        for side in ("before", "after"):
            self.assertEqual(json.loads(page.ids[side + "-plan-json"]), report[side]["plan"])
            self.assertIn(report[side]["plan_digest"], page.ids["identity"])
            self.assertIn(report["input_sha256"][side], page.ids["identity"])
        self.assertEqual(json.loads(page.ids["added-part-ids"]), ["review"])
        self.assertEqual(json.loads(page.ids["removed-part-ids"]), ["retire"])
        before = {p["id"]: p for p in report["before"]["plan"]["parts"]}
        after = {p["id"]: p for p in report["after"]["plan"]["parts"]}
        for field in ("instruction", "depends_on", "tags"):
            self.assertEqual(json.loads(page.ids["change-0-" + field + "-before"]),
                             before["draft"][field])
            self.assertEqual(json.loads(page.ids["change-0-" + field + "-after"]),
                             after["draft"][field])
        for index, row in enumerate(report["idempotency_keys"]):
            self.assertEqual(json.loads(page.ids[f"key-{index}-part"]), row["part_id"])
            self.assertEqual(json.loads(page.ids[f"key-{index}-before"]), row["before"])
            self.assertEqual(json.loads(page.ids[f"key-{index}-after"]), row["after"])
            self.assertEqual(json.loads(page.ids[f"key-{index}-changed"]), row["changed"])

    def test_authored_markup_remains_text_and_no_external_resources(self):
        page = Page(self.html())
        tags = {tag for tag, _ in page.tags}
        self.assertTrue({"html", "main", "h1", "h2", "table", "caption", "th", "pre"} <= tags)
        self.assertFalse(tags & {"script", "iframe", "object", "embed", "form", "img",
                                 "audio", "video", "link", "base", "input"})
        self.assertEqual(len(page.links), 1)
        self.assertEqual(page.links[0]["download"], "plan-comparison.json")
        for _, attrs in page.tags:
            self.assertFalse(any(name.lower().startswith("on") for name in attrs))
            self.assertNotIn("src", attrs)
        self.assertIn("</pre><script>window.CANARY", page.ids["after-plan-json"])
        self.assertIn("\\u0000", page.ids["after-plan-json"])
        self.assertIn("🌿", page.ids["after-plan-json"])

    def test_repeated_stdout_and_exclusive_file_are_identical(self):
        first = self.html()
        self.assertEqual(self.html(), first)
        destination = self.work / "comparison.html"
        self.assertEqual(self.html("--output", str(destination)), b"")
        self.assertEqual(destination.read_bytes(), first)
        self.assertEqual((self.before.read_bytes(), self.after.read_bytes()), self.original_bytes)
        self.assertNotIn(str(self.work).encode(), first)

    def test_identical_native_plans_keep_distinct_raw_input_hashes(self):
        self.after.write_bytes(json.dumps(self.old, indent=2, ensure_ascii=False).encode())
        page = Page(self.html())
        report = json.loads(page.download())
        self.assertTrue(report["same_plan"])
        self.assertNotEqual(report["input_sha256"]["before"], report["input_sha256"]["after"])
        self.assertEqual(page.ids["same-plan"], "true")
        self.assertIn("No retained part fields changed.", page.ids["changes"])
        self.assertEqual(json.loads(page.ids["added-part-ids"]), [])
        self.assertEqual(json.loads(page.ids["removed-part-ids"]), [])

    def test_reversing_inputs_reverses_native_direction(self):
        self.write(self.before, self.new)
        self.write(self.after, self.old)
        page = Page(self.html())
        self.assertEqual(json.loads(page.ids["added-part-ids"]), ["retire"])
        self.assertEqual(json.loads(page.ids["removed-part-ids"]), ["review"])
        self.assertEqual(page.download(), self.native())

    def test_project_only_edit_is_not_hidden(self):
        self.new = dict(self.old, project="review-v2")
        self.write(self.after, self.new)
        page = Page(self.html())
        self.assertEqual(page.ids["project-id-changed"], "true")
        self.assertEqual(page.ids["part-order-changed"], "false")
        self.assertEqual(page.ids["same-plan"], "false")
        self.assertEqual(json.loads(page.download())["changed_parts"], [])

    def test_malformed_second_input_has_no_html_or_destination(self):
        self.after.write_bytes(b'{"project":"bad","project":"duplicate","parts":[]}')
        target = self.work / "absent.html"
        result = self.run_cli("--format", "html", "--output", str(target))
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"duplicate JSON", result.stderr)
        self.assertFalse(target.exists())

    def test_existing_output_and_input_remain_unchanged(self):
        target = self.work / "existing.html"
        target.write_bytes(b"Retained bytes")
        for destination in (target, self.before, self.work):
            with self.subTest(destination=destination):
                result = self.run_cli("--format", "html", "--output", str(destination))
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"cannot write report", result.stderr)
                self.assertEqual(target.read_bytes(), b"Retained bytes")
                self.assertEqual((self.before.read_bytes(), self.after.read_bytes()),
                                 self.original_bytes)

    def test_input_limit_still_applies_before_html_output(self):
        self.write(self.after, {"project": "many", "parts": [
            {"id": f"part{i}", "instruction": "Work."} for i in range(257)]})
        result = self.run_cli("--format", "html")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"at most 256", result.stderr)

    def test_render_limit_refuses_before_publication(self):
        target = self.work / "absent.html"
        code = (
            "from fanout_engine import compare, compare_html; "
            "compare_html.MAX_HTML_BYTES = 1; "
            "raise SystemExit(compare.main(" + repr([
                "--before", str(self.before), "--after", str(self.after),
                "--format", "html", "--output", str(target)]) + "))"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT,
                                capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"HTML report exceeds", result.stderr)
        self.assertFalse(target.exists())

    @unittest.skipUnless(Path("/dev/full").exists(), "requires /dev/full")
    def test_html_stdout_failure_keeps_controlled_exit(self):
        with open("/dev/full", "wb", buffering=0) as sink:
            result = self.run_cli("--format", "html", stdout=sink)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"cannot write report", result.stderr)
        self.assertNotIn(b"Exception ignored", result.stderr)


if __name__ == "__main__":
    unittest.main()
