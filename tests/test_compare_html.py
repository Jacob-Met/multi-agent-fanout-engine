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


class _MobilePage(Page):
    """Observe real label text and native table relationships, without a CSS model."""
    def __init__(self, raw):
        self.mobile_tables = []
        self.current_mobile = None
        self.current_label = None
        super().__init__(raw)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "table" and "value-table" in attributes.get("class", "").split():
            self.current_mobile = {"tags": [], "labels": []}
            self.mobile_tables.append(self.current_mobile)
        if self.current_mobile is not None:
            self.current_mobile["tags"].append((tag, attributes))
            if tag == "span" and "mobile-label" in attributes.get("class", "").split():
                self.current_label = {"attributes": attributes, "text": ""}
                self.current_mobile["labels"].append(self.current_label)
        super().handle_starttag(tag, attrs)

    def handle_data(self, data):
        if self.current_label is not None:
            self.current_label["text"] += data
        super().handle_data(data)

    def handle_endtag(self, tag):
        if tag == "span":
            self.current_label = None
        if tag == "table":
            self.current_mobile = None
        super().handle_endtag(tag)


class MobileComparisonHtmlTests(unittest.TestCase):
    """Direct presentation fixtures; no comparator, CLI or ledger invocation."""
    @classmethod
    def setUpClass(cls):
        import importlib.util
        path = ROOT / "fanout_engine" / "compare_html.py"
        spec = importlib.util.spec_from_file_location("mobile_report_renderer", path)
        cls.renderer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.renderer)

    @staticmethod
    def report(mixed):
        # These literal identities are synthetic presentation values, not digests
        # derived by a second comparison implementation.
        part = {"id": "draft", "instruction": 'Read <reader> & "quotes".\n\tΩ',
                "depends_on": [], "tags": ["old"]}
        same_plan = {"project": 'review "Ω"', "parts": [part]}
        report = {
            "schema_version": 1,
            "before": {"plan": same_plan, "plan_digest": "a" * 64},
            "after": {"plan": json.loads(json.dumps(same_plan)), "plan_digest": "a" * 64},
            "same_plan": True, "project_id_changed": False, "part_order_changed": False,
            "added_part_ids": [], "removed_part_ids": [], "changed_parts": [],
            "input_sha256": {"before": "b" * 64, "after": "c" * 64},
            "idempotency_keys": [{"part_id": "draft", "before": "fanout-" + "d" * 64,
                                  "after": "fanout-" + "d" * 64, "changed": False}],
        }
        if mixed:
            report["before"]["plan"]["parts"].append(
                {"id": "removed", "instruction": "Before only", "depends_on": [], "tags": []})
            report["after"] = {
                "plan": {"project": "after Ω", "parts": [
                    {"id": "added", "instruction": "After only", "depends_on": [], "tags": []},
                    {"id": "draft", "instruction": '</pre><script>CANARY</script>\x00\r\n\t🌿',
                     "depends_on": ["added"], "tags": ['new "tag"', "Ω"]}]},
                "plan_digest": "e" * 64,
            }
            report.update(same_plan=False, project_id_changed=True, part_order_changed=True,
                          added_part_ids=["added"], removed_part_ids=["removed"],
                          changed_parts=[{"part_id": "draft", "fields": ["instruction", "depends_on", "tags"]}],
                          idempotency_keys=[
                              {"part_id": "added", "before": None, "after": "fanout-" + "f" * 64, "changed": True},
                              {"part_id": "draft", "before": "fanout-" + "d" * 64, "after": "fanout-" + "1" * 64, "changed": True},
                              {"part_id": "removed", "before": "fanout-" + "2" * 64, "after": None, "changed": True}])
        return report

    def render(self, mixed):
        report = self.report(mixed)
        native = (json.dumps(report, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
        raw = self.renderer.render_comparison(report, native)
        return report, native, raw, _MobilePage(raw)

    def test_same_and_mixed_reports_preserve_complete_values(self):
        for mixed in (False, True):
            with self.subTest(mixed=mixed):
                report, native, raw, page = self.render(mixed)
                self.assertEqual(page.download(), native)
                for side in ("before", "after"):
                    self.assertEqual(json.loads(page.ids[side + "-plan-json"]), report[side]["plan"])
                    self.assertIn(report[side]["plan_digest"], page.ids["identity"])
                    self.assertIn(report["input_sha256"][side], page.ids["identity"])
                for key, identity in (("same_plan", "same-plan"), ("project_id_changed", "project-id-changed"),
                                      ("part_order_changed", "part-order-changed"), ("added_part_ids", "added-part-ids"),
                                      ("removed_part_ids", "removed-part-ids")):
                    self.assertEqual(json.loads(page.ids[identity]), report[key])
                for index, row in enumerate(report["idempotency_keys"]):
                    for key, suffix in (("part_id", "part"), ("before", "before"), ("after", "after"), ("changed", "changed")):
                        self.assertEqual(json.loads(page.ids[f"key-{index}-{suffix}"]), row[key])
                if mixed:
                    self.assertEqual(page.ids["key-0-before"], "null")
                    self.assertEqual(page.ids["key-2-after"], "null")
                    for field in ("instruction", "depends_on", "tags"):
                        self.assertEqual(json.loads(page.ids[f"change-0-{field}-before"]), report["before"]["plan"]["parts"][0][field])
                        self.assertEqual(json.loads(page.ids[f"change-0-{field}-after"]), report["after"]["plan"]["parts"][1][field])
                else:
                    self.assertIn("No retained part fields changed.", page.ids["changes"])

    def test_mobile_table_labels_and_semantic_structure(self):
        for mixed in (False, True):
            with self.subTest(mixed=mixed):
                report, _, _, page = self.render(mixed)
                self.assertEqual(len(page.mobile_tables), 2)
                identity, keys = page.mobile_tables
                self.assertEqual([x["text"] for x in identity["labels"]], ["Before", "After"] * 3)
                self.assertEqual([x["text"] for x in keys["labels"]],
                                 ["Part ID", "Before key", "After key", "Changed"] * len(report["idempotency_keys"]))
                for table in page.mobile_tables:
                    tags = table["tags"]
                    self.assertEqual(tags[0][1]["role"], "table")
                    self.assertIn(tags[0][1]["aria-labelledby"], page.ids)
                    self.assertEqual(sum(tag == "caption" for tag, _ in tags), 1)
                    for tag, attributes in tags:
                        if tag in ("thead", "tbody"):
                            self.assertEqual(attributes["role"], "rowgroup")
                        elif tag == "tr":
                            self.assertEqual(attributes["role"], "row")
                        elif tag == "th":
                            self.assertEqual(attributes["role"], {"col": "columnheader", "row": "rowheader"}[attributes["scope"]])
                        elif tag == "td":
                            self.assertEqual(attributes["role"], "cell")
                    self.assertTrue(all(x["attributes"].get("aria-hidden") == "true" for x in table["labels"]))

    def test_markup_is_inert_and_download_preserves_supplied_bytes(self):
        for mixed in (False, True):
            with self.subTest(mixed=mixed):
                report = self.report(mixed)
                # Whitespace and a CRLF are deliberately supplied to the renderer;
                # this test requires exact custody, not JSON reserialization.
                supplied = (" \n" + json.dumps(report, ensure_ascii=False, indent=1) + "\r\n").encode()
                page = _MobilePage(self.renderer.render_comparison(report, supplied))
                self.assertEqual(page.download(), supplied)
                self.assertEqual(len(page.links), 1)
                self.assertFalse({tag for tag, _ in page.tags} & {"script", "iframe", "object", "embed", "img", "link", "form"})
                for _, attrs in page.tags:
                    self.assertFalse(any(name.lower().startswith("on") for name in attrs))
                    self.assertNotIn("src", attrs)
                if mixed:
                    self.assertIn("</pre><script>CANARY</script>", page.ids["after-plan-json"])
                    self.assertIn("\\u0000", page.ids["after-plan-json"])
                    self.assertIn("🌿", page.ids["after-plan-json"])

    def test_render_is_repeatable_immutable_and_limited(self):
        report = self.report(True)
        snapshot = json.dumps(report, ensure_ascii=False)
        native = (snapshot + "\n").encode()
        first = self.renderer.render_comparison(report, native)
        self.assertEqual(self.renderer.render_comparison(report, native), first)
        self.assertEqual(json.dumps(report, ensure_ascii=False), snapshot)
        old_limit = self.renderer.MAX_HTML_BYTES
        try:
            self.renderer.MAX_HTML_BYTES = len(first) - 1
            with self.assertRaisesRegex(ValueError, "HTML report exceeds the 32 MiB consumer limit"):
                self.renderer.render_comparison(report, native)
        finally:
            self.renderer.MAX_HTML_BYTES = old_limit
        self.assertEqual(json.dumps(report, ensure_ascii=False), snapshot)


if __name__ == "__main__":
    unittest.main()
