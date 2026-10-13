"""Receive authored plan comparisons through exclusive file publication."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def snapshot(path):
    metadata = path.stat()
    return path.read_bytes(), metadata.st_ino, metadata.st_mtime_ns


class CompareExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fanout-compare-export-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.before = self.directory / "original 東京.json"
        self.after = self.directory / "revised # & %.json"
        self.before.write_text(json.dumps({
            "project": "review",
            "parts": [
                {"id": "research", "instruction": "Read the notes."},
                {"id": "draft", "instruction": "Write the draft.", "depends_on": ["research"]},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        self.after.write_text(json.dumps({
            "project": "review",
            "parts": [
                {"id": "research", "instruction": "Read the notes."},
                {"id": "draft", "instruction": "Write the cited draft — 東京.", "depends_on": ["research"]},
                {"id": "verify", "instruction": "Review the draft.", "depends_on": ["draft"]},
            ],
        }, ensure_ascii=False), encoding="utf-8")

    def run_cli(self, output=None, *, after=None):
        arguments = [
            sys.executable, "-S", "-B", "-m", "fanout_engine.compare",
            "--before", str(self.before),
            "--after", str(self.after if after is None else after),
        ]
        if output is not None:
            arguments += ["--output", str(output)]
        return subprocess.run(arguments, cwd=ROOT, capture_output=True, timeout=10)

    def assert_no_stage(self):
        self.assertFalse(any(path.name.startswith(".fanout-")
                             for path in self.directory.iterdir()))

    def assert_output_refused(self, result):
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"fanout compare: cannot write report:", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        self.assert_no_stage()

    def test_new_file_matches_stdout_and_preserves_both_inputs(self):
        output = self.directory / "comparison 東京 # & %.json"
        inputs_before = (snapshot(self.before), snapshot(self.after))
        stdout = self.run_cli()
        self.assertEqual(stdout.returncode, 0, stdout.stderr)
        self.assertEqual(stdout.stderr, b"")
        exported = self.run_cli(output)
        self.assertEqual(exported.returncode, 0, exported.stderr)
        self.assertEqual(exported.stdout, b"")
        self.assertEqual(exported.stderr, b"")
        self.assertEqual(output.read_bytes(), stdout.stdout)
        report = json.loads(output.read_bytes())
        self.assertEqual(report["added_part_ids"], ["verify"])
        self.assertEqual(report["changed_parts"], [
            {"part_id": "draft", "fields": ["instruction"]},
        ])
        self.assertEqual(report["input_sha256"], {
            "before": hashlib.sha256(inputs_before[0][0]).hexdigest(),
            "after": hashlib.sha256(inputs_before[1][0]).hexdigest(),
        })
        self.assertTrue(output.read_bytes().endswith(b"\n"))
        self.assertEqual((snapshot(self.before), snapshot(self.after)), inputs_before)
        self.assert_no_stage()

    def test_existing_destinations_and_both_input_aliases_are_preserved(self):
        existing = self.directory / "existing.json"
        existing.write_bytes(b"previous comparison\n")
        destinations = [existing, self.before, self.after, self.directory]
        links = []
        for label, source in (("before", self.before), ("after", self.after)):
            hardlink = self.directory / (label + "-hardlink")
            os.link(source, hardlink)
            destinations.append(hardlink)
            if os.name != "nt":
                symlink = self.directory / (label + "-symlink")
                symlink.symlink_to(source)
                destinations.append(symlink)
                links.append((symlink, os.readlink(symlink)))
        if os.name != "nt":
            dangling = self.directory / "dangling"
            dangling.symlink_to(self.directory / "absent-target")
            destinations.append(dangling)
            links.append((dangling, os.readlink(dangling)))
        inputs_before = (snapshot(self.before), snapshot(self.after))
        existing_before = snapshot(existing)
        for destination in destinations:
            with self.subTest(destination=destination):
                self.assert_output_refused(self.run_cli(destination))
        self.assertEqual((snapshot(self.before), snapshot(self.after)), inputs_before)
        self.assertEqual(snapshot(existing), existing_before)
        for link, target in links:
            self.assertTrue(link.is_symlink())
            self.assertEqual(os.readlink(link), target)
        self.assertFalse((self.directory / "absent-target").exists())

    def test_invalid_or_missing_second_input_creates_no_report(self):
        output = self.directory / "comparison.json"
        self.after.write_bytes(b'{"project":"review","parts":[{"id":"last","instruction":"Read","depends_on":["last"]}]}')
        inputs_before = (snapshot(self.before), snapshot(self.after))
        missing = self.directory / "missing.json"
        for after in (self.after, missing):
            with self.subTest(after=after):
                result = self.run_cli(output, after=after)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"fanout compare: cannot compare plans:", result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)
                self.assertFalse(output.exists())
                self.assert_no_stage()
        self.assertFalse(missing.exists())
        self.assertEqual((snapshot(self.before), snapshot(self.after)), inputs_before)

    def test_missing_output_parent_is_an_output_failure(self):
        output = self.directory / "absent-directory" / "comparison.json"
        inputs_before = (snapshot(self.before), snapshot(self.after))
        self.assert_output_refused(self.run_cli(output))
        self.assertFalse(output.parent.exists())
        self.assertEqual((snapshot(self.before), snapshot(self.after)), inputs_before)


if __name__ == "__main__":
    unittest.main()
