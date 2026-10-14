"""Receive exact draft comparisons through the native API and real CLI."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import Part, Plan, canonical_json
from fanout_engine.compare import ComparisonError, compare_plans

ROOT = Path(__file__).resolve().parents[1]


class ComparePlansTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory(prefix="fanout-compare-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        punctuation = "#%" if os.name == "nt" else "#?%"
        self.before_path = self.root / f"before {punctuation} café.json"
        self.after_path = self.root / "after & revised.json"
        self.before = Plan("review", (
            Part("write", "Write the first draft.", ("source",), ("draft",)),
            Part("source", "Read the sources."),
            Part("old", "An earlier deliverable."),
        ))
        self.after = Plan("review", (
            Part("source", "Read the sources."),
            Part("write", "Write the revised draft.", ("source",), ("checked",)),
            Part("new", "Review the revised draft.", ("write",)),
        ))
        self.before_path.write_text(canonical_json(self.before.to_dict()), encoding="utf-8")
        self.after_path.write_text(canonical_json(self.after.to_dict()), encoding="utf-8")

    def cli(self, *arguments: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.compare", *arguments],
            cwd=ROOT, capture_output=True, timeout=10,
        )

    def run_pair(self) -> subprocess.CompletedProcess[bytes]:
        return self.cli("--before", str(self.before_path), "--after", str(self.after_path))

    def test_exact_edits_and_complete_key_identity(self) -> None:
        report = compare_plans(self.before, self.after)
        self.assertEqual(report["before"], {"plan": self.before.to_dict(), "plan_digest": self.before.digest})
        self.assertEqual(report["after"], {"plan": self.after.to_dict(), "plan_digest": self.after.digest})
        self.assertFalse(report["same_plan"])
        self.assertFalse(report["project_id_changed"])
        self.assertTrue(report["part_order_changed"])
        self.assertEqual(report["added_part_ids"], ["new"])
        self.assertEqual(report["removed_part_ids"], ["old"])
        self.assertEqual(report["changed_parts"], [{"part_id": "write", "fields": ["instruction", "tags"]}])
        self.assertEqual([row["part_id"] for row in report["idempotency_keys"]], ["source", "write", "new", "old"])
        for row in report["idempotency_keys"]:
            self.assertTrue(row["changed"])
            for label, plan in (("before", self.before), ("after", self.after)):
                if row["part_id"] in {part.id for part in plan.parts}:
                    material = (plan.project_id + "\0" + plan.digest + "\0" + row["part_id"]).encode("utf-8")
                    self.assertEqual(row[label], "fanout-" + hashlib.sha256(material).hexdigest())
                else:
                    self.assertIsNone(row[label])

    def test_equal_native_plans_with_distinct_file_bytes(self) -> None:
        left = {"project": "same", "parts": [{"id": "a", "instruction": "Keep it.", "tags": ["z", "a", "z"]}]}
        right = {"parts": [{"instruction": "Keep it.", "id": "a", "tags": ["a", "z"], "depends_on": []}], "project": "same"}
        self.before_path.write_text(json.dumps(left, indent=2), encoding="utf-8")
        self.after_path.write_text(canonical_json(right), encoding="utf-8")
        result = self.run_pair()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["same_plan"])
        self.assertFalse(report["part_order_changed"])
        self.assertEqual(report["changed_parts"], [])
        self.assertEqual(report["added_part_ids"], [])
        self.assertEqual(report["removed_part_ids"], [])
        self.assertFalse(report["idempotency_keys"][0]["changed"])
        self.assertNotEqual(report["input_sha256"]["before"], report["input_sha256"]["after"])

    def test_project_or_declaration_order_changes_rotate_unchanged_part_keys(self) -> None:
        original = Plan("first", (Part("a", "A"), Part("b", "B")))
        for revised, project_changed, order_changed in (
            (Plan("second", original.parts), True, False),
            (Plan("first", tuple(reversed(original.parts))), False, True),
        ):
            with self.subTest(project=revised.project_id, order=order_changed):
                report = compare_plans(original, revised)
                self.assertEqual(report["project_id_changed"], project_changed)
                self.assertEqual(report["part_order_changed"], order_changed)
                self.assertEqual(report["changed_parts"], [])
                self.assertFalse(report["same_plan"])
                self.assertTrue(all(row["changed"] for row in report["idempotency_keys"]))

    def test_direct_constructor_dependency_order_and_repeated_tags_survive(self) -> None:
        original = Plan("p", (Part("one", "1"), Part("two", "2"),
                              Part("use", "Use both.", ("one", "two"), ("tag", "tag"))))
        revised = Plan("p", (Part("one", "1"), Part("two", "2"),
                             Part("use", "Use both.", ("two", "one"), ("tag",))))
        report = compare_plans(original, revised)
        self.assertEqual(report["changed_parts"], [{"part_id": "use", "fields": ["depends_on", "tags"]}])
        self.assertEqual(report["before"]["plan"]["parts"][2]["tags"], ["tag", "tag"])
        report["before"]["plan"]["parts"][2]["depends_on"].clear()
        self.assertEqual(original.parts[2].depends_on, ("one", "two"))
        self.assertEqual(compare_plans(original, original)["changed_parts"], [])

    def test_changed_admitted_part_like_source_is_refused_before_report(self) -> None:
        class MutablePart:
            id = "a"
            instruction = "Original"
            depends_on = ()
            tags = ()

            def to_dict(self):
                return {"id": self.id, "instruction": self.instruction, "depends_on": [], "tags": []}

        part = MutablePart()
        original = Plan("p", (part,))
        self.assertTrue(compare_plans(original, original)["same_plan"])
        part.instruction = "Revised after validation"
        with self.assertRaisesRegex(ComparisonError, "changed since validation"):
            compare_plans(original, Plan("p", (Part("a", "Original"),)))

    def test_cli_is_exact_repeatable_and_preserves_literal_inputs(self) -> None:
        before_bytes = self.before_path.read_bytes()
        after_bytes = self.after_path.read_bytes()
        siblings = sorted(path.name for path in self.root.iterdir())
        result = self.run_pair()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, b"")
        expected = compare_plans(self.before, self.after)
        expected["input_sha256"] = {"before": hashlib.sha256(before_bytes).hexdigest(),
                                    "after": hashlib.sha256(after_bytes).hexdigest()}
        self.assertEqual(result.stdout, (canonical_json(expected) + "\n").encode("utf-8"))
        self.assertEqual(self.run_pair().stdout, result.stdout)
        self.assertEqual(self.before_path.read_bytes(), before_bytes)
        self.assertEqual(self.after_path.read_bytes(), after_bytes)
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), siblings)

    def test_invalid_second_input_never_emits_a_partial_comparison(self) -> None:
        malformed = [b"{", b"\xff", b'{"project":"p","project":"q","parts":[]}',
                     b'{"project":"p","parts":[{"id":"a","instruction":"A","depends_on":["a"]}]}',
                     b'{"project":"p","parts":[{"id":"a","instruction":"A","extra":NaN}]}',
                     b'{"project":"p","parts":[{"id":"a","instruction":"A","depends_on":["missing"]}]}']
        for content in malformed:
            with self.subTest(content=content):
                self.after_path.write_bytes(content)
                result = self.run_pair()
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"cannot compare plans", result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)

    def test_input_part_and_api_report_limits(self) -> None:
        self.after_path.write_bytes(b" " * (1024 * 1024 + 1))
        result = self.run_pair()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"1 MiB", result.stderr)
        large = Plan("p", tuple(Part(f"p{i}", "A") for i in range(257)))
        self.after_path.write_text(canonical_json(large.to_dict()), encoding="utf-8")
        result = self.run_pair()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"256 parts", result.stderr)
        with self.assertRaisesRegex(ComparisonError, "256 parts"):
            compare_plans(self.before, large)
        with self.assertRaisesRegex(ComparisonError, "native Plan"):
            compare_plans(self.before.to_dict(), self.after)
        huge = Plan("p", (Part("a", "x" * (3 * 1024 * 1024)),))
        with self.assertRaisesRegex(ComparisonError, "4 MiB"):
            compare_plans(huge, huge)

    def test_missing_directory_and_fifo_inputs_do_not_create_or_block(self) -> None:
        inputs = [self.root / "missing-parent" / "missing.json", self.root]
        if hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"):
            fifo = self.root / "input.pipe"
            os.mkfifo(fifo)
            inputs.append(fifo)
        for path in inputs:
            with self.subTest(path=path):
                result = self.cli("--before", str(self.before_path), "--after", str(path))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
                self.assertNotIn(b"Traceback", result.stderr)
        self.assertFalse((self.root / "missing-parent").exists())

    @unittest.skipUnless(Path("/dev/full").exists(), "requires /dev/full")
    def test_failed_output_is_not_success_or_a_shutdown_traceback(self) -> None:
        with open("/dev/full", "wb") as output:
            result = subprocess.run(
                [sys.executable, "-B", "-m", "fanout_engine.compare", "--before", str(self.before_path),
                 "--after", str(self.after_path)], cwd=ROOT, stdout=output,
                stderr=subprocess.PIPE, timeout=10,
            )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(b"cannot write report", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)
        self.assertNotIn(b"Exception ignored", result.stderr)



    def test_exclusive_output_matches_stdout_and_preserves_inputs(self) -> None:
        before = self.before_path.read_bytes()
        after = self.after_path.read_bytes()
        expected = self.run_pair()
        self.assertEqual(expected.returncode, 0, expected.stderr)
        destination = self.root / "result résumé.json"
        result = self.cli("--before", str(self.before_path), "--after", str(self.after_path),
                          "--output", str(destination))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        self.assertEqual(destination.read_bytes(), expected.stdout)
        self.assertEqual(self.before_path.read_bytes(), before)
        self.assertEqual(self.after_path.read_bytes(), after)
        self.assertEqual(list(self.root.glob(".fanout-preview-*")), [])

    def test_exclusive_output_refuses_existing_and_missing_parent(self) -> None:
        original_before = self.before_path.read_bytes()
        original_after = self.after_path.read_bytes()
        occupied = self.root / "occupied.json"
        occupied.write_bytes(b"not a comparison")
        directory = self.root / "directory"
        directory.mkdir()
        symlink = self.root / "symlink.json"
        destinations = [occupied, directory, self.root / "missing" / "new.json",
                        self.before_path, self.after_path]
        try:
            symlink.symlink_to(occupied)
        except (OSError, NotImplementedError):
            # Symlink privileges vary on Windows; other refusal cases always run.
            pass
        else:
            destinations.append(symlink)
        for destination in destinations:
            with self.subTest(destination=destination):
                result = self.cli("--before", str(self.before_path), "--after", str(self.after_path),
                                  "--output", str(destination))
                self.assertEqual((result.returncode, result.stdout), (1, b""), result.stderr)
                self.assertIn(b"cannot write report", result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)
        self.assertEqual(occupied.read_bytes(), b"not a comparison")
        self.assertEqual(self.before_path.read_bytes(), original_before)
        self.assertEqual(self.after_path.read_bytes(), original_after)
        self.assertEqual(list(self.root.glob(".fanout-preview-*")), [])
        self.assertFalse((self.root / "missing").exists())

    def test_invalid_second_plan_with_output_does_not_create_file(self) -> None:
        destination = self.root / "must-remain-absent.json"
        self.after_path.write_bytes(b'{"project":"p","parts":[}')
        before = self.before_path.read_bytes()
        after = self.after_path.read_bytes()
        result = self.cli("--before", str(self.before_path), "--after", str(self.after_path),
                          "--output", str(destination))
        self.assertEqual((result.returncode, result.stdout), (2, b""), result.stderr)
        self.assertIn(b"cannot compare plans", result.stderr)
        self.assertFalse(destination.exists())
        self.assertEqual(self.before_path.read_bytes(), before)
        self.assertEqual(self.after_path.read_bytes(), after)

if __name__ == "__main__":
    unittest.main()
