"""Retained offline review makes bidi formatting controls visible as text."""
from __future__ import annotations

import base64
from html.parser import HTMLParser
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fanout_engine.inspection import inspect_project
from fanout_engine.ledger import Ledger
from fanout_engine.plan import Plan, canonical_json

ROOT = Path(__file__).resolve().parents[1]
# Arabic letter mark, left/right marks, embeddings/overrides/pop, and isolates/pop.
FORMATTING = "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069"
ORDINARY = "العربية עברית café 雪 👩\u200d💻"


class Page(HTMLParser):
    def __init__(self, document):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.downloads = []
        self.feed(document)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "download" in attrs:
            self.downloads.append(attrs["href"])

    def handle_data(self, data):
        self.text.append(data)


class ProjectReviewBidiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.database = self.work / "retained.sqlite3"
        self.output = self.work / "review.html"
        self.project = "formatting"
        self.part = "formatting-part"
        with Ledger(str(self.database)) as ledger:
            for project, part, label in (
                (self.project, self.part, "label-" + FORMATTING + "-end"),
                ("ordinary", "ordinary-part", ORDINARY),
            ):
                plan = Plan.from_dict({"project": project, "parts": [
                    {"id": part, "instruction": label + ' <b>&literal</b>', "tags": ["local"]},
                ]})
                ledger.record_plan(plan)
                ledger.mark_dispatching(project, part, "worker-" + label,
                                        {"model": label, "effort": "low"})
                ledger.mark_running(project, part, "task-" + label)
                ledger.mark_completed(project, part, "artifact-" + label, {"source": "authored", "locator": "local:" + label, "finding": label})
            self.expected = {project: inspect_project(ledger, project)
                             for project in (self.project, "ordinary")}
        self.before = self.database.read_bytes()
        self.mtime = self.database.stat().st_mtime_ns

    def run_review(self, project):
        result = subprocess.run(
            [sys.executable, "-B", *(["-O"] if sys.flags.optimize else []),
             "-m", "fanout_engine.review", "--database", str(self.database),
             "--project", project, "--output", str(self.output)],
            cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            capture_output=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")
        self.assertEqual(self.database.read_bytes(), self.before)
        self.assertEqual(self.database.stat().st_mtime_ns, self.mtime)
        self.assertFalse(any(Path(str(self.database) + suffix).exists()
                             for suffix in ("-wal", "-shm", "-journal")))
        return self.output.read_bytes()

    def test_bidi_formatting_is_visible_in_all_rendered_text(self):
        document = self.run_review(self.project).decode("utf-8")
        text = "".join(Page(document).text)
        for character in FORMATTING:
            self.assertNotIn(character, document)
            self.assertIn(f"\\u{ord(character):04x}", text)
        escaped = "".join(f"\\u{ord(character):04x}" for character in FORMATTING)
        for prefix in ("label-", "worker-label-",
                       "task-label-", "artifact-label-"):
            self.assertIn(prefix + escaped + "-end", text)
        self.assertIn("<b>&literal</b>", text)

    def test_download_keeps_exact_native_formatting_characters(self):
        document = self.run_review(self.project).decode("utf-8")
        downloads = Page(document).downloads
        self.assertEqual(len(downloads), 1)
        prefix, encoded = downloads[0].split(",", 1)
        self.assertEqual(prefix, "data:application/json;base64")
        payload = base64.b64decode(encoded, validate=True)
        expected = (canonical_json(self.expected[self.project]) + "\n").encode("utf-8")
        self.assertEqual(payload, expected)
        for character in FORMATTING:
            self.assertIn(character.encode("utf-8"), payload)

    def test_ordinary_rtl_letters_unicode_and_joiner_remain_literal(self):
        document = self.run_review("ordinary").decode("utf-8")
        text = "".join(Page(document).text)
        self.assertIn(ORDINARY + " <b>&literal</b>", text)
        self.assertIn("worker-" + ORDINARY, text)
        self.assertIn("task-" + ORDINARY, text)
        self.assertIn("artifact-" + ORDINARY, text)
        self.assertNotIn(r"\u200d", text)
        payload = base64.b64decode(Page(document).downloads[0].split(",", 1)[1], validate=True)
        self.assertEqual(payload, (canonical_json(self.expected["ordinary"]) + "\n").encode("utf-8"))


if __name__ == "__main__":
    unittest.main()

