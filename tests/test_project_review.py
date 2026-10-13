"""Actual offline review CLI over retained native SQLite state."""
from __future__ import annotations

import base64
from contextlib import closing
from html.parser import HTMLParser
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from fanout_engine.inspection import inspect_project
from fanout_engine.ledger import Ledger
from fanout_engine.plan import Plan, canonical_json


ROOT = Path(__file__).resolve().parents[1]


class ParsedPage(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.tags = []
        self.text = []
        self.downloads = []
        self.references = []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attributes = dict(attrs)
        if tag == "a" and "download" in attributes:
            self.downloads.append(attributes)
        self.references.extend(value for name, value in attrs
                               if name in ("src", "href", "action"))

    def handle_data(self, data):
        self.text.append(data)


class ProjectReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "retained café.sqlite3"
        self.project = "retained-handoff"
        self.instruction = 'Read <img src="https://invalid.example/x"> & keep\x00\x0b literal.'
        self.evidence = {"source": "authored <b>source</b>",
                         "locator": "https://invalid.example/evidence?a=1&b=2",
                         "finding": "Observed only; no external proof."}
        plan = Plan.from_dict({"project": self.project, "parts": [
            {"id": "done", "instruction": self.instruction, "tags": ["review", "local"]},
            {"id": "active", "instruction": "Retain accepted work."},
            {"id": "failed", "instruction": "Retain terminal failure."},
            {"id": "unknown", "instruction": "Do not replay uncertain work."},
            {"id": "starting", "instruction": "Leave dispatching unchanged."},
            {"id": "ready", "instruction": "Observed ready only.", "depends_on": ["done"]},
            {"id": "blocked", "instruction": "Keep both direct blockers.",
             "depends_on": ["failed", "unknown"]},
        ]})
        with Ledger(str(self.database)) as ledger:
            ledger.record_plan(plan)
            for part in ("done", "active", "failed", "unknown", "starting"):
                ledger.mark_dispatching(self.project, part, "worker-Ω", {"model": "local", "effort": "low"})
                if part != "starting":
                    ledger.mark_running(self.project, part, "task-" + part)
            ledger.mark_completed(self.project, "done", "artifact:<b>literal</b>", self.evidence)
            ledger.mark_failed(self.project, "failed", self.evidence)
            ledger.mark_outcome_unknown(self.project, "unknown", self.evidence)
            self.expected = inspect_project(ledger, self.project)
        self.database_before = self.database.read_bytes()
        self.output = self.root / "review.html"

    def run_cli(self, *, project=None, database=None, output=None):
        result = subprocess.run(
            [sys.executable, *(["-O"] if sys.flags.optimize else []), "-B", "-m", "fanout_engine.review",
             "--database", str(database or self.database),
             "--project", self.project if project is None else project,
             "--output", str(output or self.output)],
            cwd=ROOT, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            capture_output=True, timeout=15)
        return result

    def assert_unchanged(self):
        self.assertEqual(self.database.read_bytes(), self.database_before)
        self.assertFalse(any(Path(str(self.database) + suffix).exists()
                             for suffix in ("-wal", "-shm", "-journal")))

    def test_native_fixture_contract_before_html_projection(self):
        self.assertEqual(self.expected["state_counts"], {
            "completed": 1, "dispatching": 1, "failed": 1,
            "outcome_unknown": 1, "queued": 2, "running": 1})
        self.assertEqual(self.expected["queued_ready_ids"], ["ready"])
        self.assertEqual(self.expected["blocked_queued_ids"], ["blocked"])
        self.assertEqual(self.expected["parts"][-1]["unmet_dependencies"], [
            {"id": "failed", "state": "failed"},
            {"id": "unknown", "state": "outcome_unknown"}])
        self.assertEqual(self.expected["parts"][0]["instruction"], self.instruction)
        self.assertEqual(self.expected["parts"][0]["evidence"], self.evidence)
        self.assert_unchanged()

    def test_complete_snapshot_and_exact_download_survive_handoff(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(result.stderr, b"")
        page = ParsedPage(self.output.read_text(encoding="utf-8"))
        self.assertEqual(len(page.downloads), 1)
        link = page.downloads[0]
        self.assertEqual(link["download"], "project-inspection.json")
        prefix, encoded = link["href"].split(",", 1)
        self.assertEqual(prefix, "data:application/json;base64")
        expected = (canonical_json(self.expected) + "\n").encode("utf-8")
        self.assertEqual(base64.b64decode(encoded, validate=True), expected)
        visible = "".join(page.text)
        for text in (self.project, self.expected["plan_digest"], "outcome_unknown", "dispatching",
                     "queued", "failed", "completed", "running", "worker-Ω", "task-active",
                     "artifact:<b>literal</b>", self.evidence["locator"], self.evidence["finding"]):
            self.assertIn(text, visible)
        for part in self.expected["parts"]:
            self.assertIn(part["idempotency_key"], visible)
            self.assertIn(str(part["updated_at"]), visible)
        self.assert_unchanged()

    def test_source_text_is_literal_and_page_has_no_active_or_external_content(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        source = self.output.read_text(encoding="utf-8")
        page = ParsedPage(source)
        self.assertTrue({"html", "title", "h1", "table", "th", "details", "summary"}.issubset(page.tags))
        self.assertFalse(set(page.tags) & {"script", "img", "iframe", "object", "embed", "form", "link"})
        self.assertNotIn("\x00", source)
        self.assertNotIn("\x0b", source)
        self.assertIn(r"\u0000", "".join(page.text))
        self.assertIn(r"\u000b", "".join(page.text))
        self.assertIn('<img src="https://invalid.example/x">', "".join(page.text))
        self.assertTrue(all(ref.startswith(("data:application/json;base64,", "#")) for ref in page.references))
        self.assert_unchanged()

    def test_same_snapshot_yields_same_page_and_keeps_authored_part_order(self):
        first = self.run_cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        other = self.root / "copy.html"
        second = self.run_cli(output=other)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(other.read_bytes(), self.output.read_bytes())
        # Each detailed part heading identifies the original declared occurrence.
        source = other.read_text(encoding="utf-8")
        headings = []
        class Headings(HTMLParser):
            in_heading = False
            def handle_starttag(self, tag, attrs):
                self.in_heading = tag == "h3"
            def handle_endtag(self, tag):
                if tag == "h3": self.in_heading = False
            def handle_data(self, data):
                if self.in_heading: headings.append(data)
        Headings().feed(source)
        self.assertEqual(headings, [part["id"] for part in self.expected["parts"]])
        self.assert_unchanged()

    def test_missing_project_and_missing_database_publish_nothing(self):
        missing = self.run_cli(project="not recorded")
        self.assertEqual(missing.returncode, 3, missing.stderr)
        self.assertIn(b"project_not_found", missing.stderr)
        self.assertFalse(self.output.exists())
        absent = self.root / "absent.sqlite3"
        result = self.run_cli(database=absent)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse(absent.exists())
        self.assertFalse(self.output.exists())
        self.assert_unchanged()

    def test_malformed_record_is_refused_before_publication(self):
        with closing(sqlite3.connect(self.database)) as connection:
            with connection:
                connection.execute("UPDATE parts SET evidence_json=? WHERE part_id='active'", ('{"broken":NaN}',))
        self.database_before = self.database.read_bytes()
        result = self.run_cli()
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn(b"invalid_record", result.stderr)
        self.assertFalse(self.output.exists())
        self.assert_unchanged()

    def test_existing_output_and_sqlite_sidecars_remain_untouched(self):
        self.output.write_bytes(b"previous handoff\x00\xff")
        result = self.run_cli()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b"cannot write report", result.stderr)
        self.assertEqual(self.output.read_bytes(), b"previous handoff\x00\xff")
        for suffix in ("-wal", "-shm", "-journal"):
            destination = Path(str(self.database) + suffix)
            result = self.run_cli(output=destination)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn(b"cannot write report", result.stderr)
            self.assertFalse(destination.exists())
        self.assert_unchanged()


if __name__ == "__main__":
    unittest.main()
