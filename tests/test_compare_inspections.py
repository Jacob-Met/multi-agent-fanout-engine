"""Saved-value comparison and actual CLI file/publication behavior."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fanout_engine.compare_inspections import (
    InspectionComparisonError, MAX_INPUT_BYTES, MAX_REPORT_BYTES, compare_inspections, main,
)

ROOT = Path(__file__).resolve().parents[1]


def raw(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def document(parts=None):
    return {"project_id": "saved project", "plan_digest": "declared digest",
            "parts": [{"id": "audit", "state": "outcome_unknown"}] if parts is None else parts}


class SavedInspectionComparisonTests(unittest.TestCase):
    def test_complete_values_unknown_fields_and_typed_differences(self):
        first = document([{"id": "audit", "kind": True, "number": 1, "zero": -0.0,
                           "removed": None, "order": [1, 2]}])
        second = document([{"id": "audit", "kind": 1, "number": 1.0, "zero": 0.0,
                            "added": None, "order": [2, 1]}])
        first["opaque"] = {"huge": 10**80, "state": "not native-validated", "text": " \u2603 "}
        second["opaque"] = copy.deepcopy(first["opaque"])
        first["retired"] = None
        second["new"] = False
        result = compare_inspections(raw(first), raw(second))
        self.assertEqual(result["schema"], "fanout.saved-inspection-comparison/1")
        self.assertIs(result["saved_data_only"], True)
        self.assertEqual(raw(result["first"]["document"]), raw(first))
        self.assertEqual(raw(result["second"]["document"]), raw(second))
        self.assertEqual([x["field"] for x in result["top_level_changes"]], ["new", "retired"])
        changes = result["part_changes"][0]["fields"]
        self.assertEqual([x["field"] for x in changes],
                         ["added", "kind", "number", "order", "removed", "zero"])
        self.assertEqual(changes[0], {"field": "added", "first": {"present": False},
                                     "second": {"present": True, "value": None}})
        self.assertEqual(changes[4], {"field": "removed", "first": {"present": True, "value": None},
                                     "second": {"present": False}})
        self.assertIs(type(changes[1]["first"]["value"]), bool)
        self.assertIs(type(changes[1]["second"]["value"]), int)
        self.assertIs(type(changes[2]["first"]["value"]), int)
        self.assertIs(type(changes[2]["second"]["value"]), float)
        self.assertEqual(json.dumps(changes[-1]["first"]["value"]), "-0.0")
        self.assertEqual(json.dumps(changes[-1]["second"]["value"]), "0.0")

    def test_raw_identity_is_separate_from_saved_values(self):
        value = document()
        first = raw(value)
        second = json.dumps(dict(reversed(list(value.items()))), indent=3).encode()
        result = compare_inspections(first, second)
        self.assertFalse(result["same_input_bytes"])
        self.assertTrue(result["same_saved_values"])
        self.assertEqual(result["top_level_changes"], [])
        self.assertEqual(result["part_changes"], [])
        for side, data in (("first", first), ("second", second)):
            self.assertEqual(result[side]["input_bytes"], len(data))
            self.assertEqual(result[side]["input_sha256"], hashlib.sha256(data).hexdigest())
        identical = compare_inspections(first, first)
        self.assertTrue(identical["same_input_bytes"])
        self.assertTrue(identical["same_saved_values"])
        self.assertEqual(identical["changed_part_ids"], [])

    def test_part_order_and_first_order_change_rows(self):
        first = document([{"id": "z", "value": 1}, {"id": "a", "value": 2}])
        second = document(list(reversed(copy.deepcopy(first["parts"]))))
        ordered = compare_inspections(raw(first), raw(second))
        self.assertTrue(ordered["part_order_changed"])
        self.assertFalse(ordered["same_saved_values"])
        self.assertEqual(ordered["part_changes"], [])
        for part in second["parts"]:
            part["value"] = 3
        changed = compare_inspections(raw(first), raw(second))
        self.assertEqual(changed["changed_part_ids"], ["z", "a"])
        swapped = compare_inspections(raw(second), raw(first))
        self.assertEqual(swapped["changed_part_ids"], ["a", "z"])
        self.assertEqual(swapped["part_changes"][0]["fields"][0]["first"]["value"], 3)

    def test_shape_only_empty_parts_whitespace_and_lexical_integer_zero(self):
        empty = {"project_id": " ", "plan_digest": "\t", "parts": [], "other": "retained"}
        self.assertTrue(compare_inspections(raw(empty), raw(empty))["same_saved_values"])
        first = b'{"project_id":"p","plan_digest":"d","parts":[{"id":" ","value":-0}]}'
        second = first.replace(b':-0}', b':0}')
        result = compare_inspections(first, second)
        self.assertFalse(result["same_input_bytes"])
        self.assertTrue(result["same_saved_values"])

    def test_reject_invalid_json_or_utf8_before_comparison(self):
        good = raw(document())
        invalid = [b'{"project_id":"p","project_id":"q"}', b'{"value":NaN}',
                   b'{"value":Infinity}', b'{"value":1e400}', b'{"value":"\\ud800"}',
                   b"\xff", b"[]", b"null", b"3", b"{}"]
        for bad in invalid:
            with self.subTest(input=bad):
                with self.assertRaises(ValueError):
                    compare_inspections(bad, good)
        with self.assertRaises(InspectionComparisonError):
            compare_inspections(good.decode(), good)

    def test_reject_ambiguous_shape_and_relationships(self):
        good = document()
        invalid = [
            {**good, "project_id": ""}, {**good, "plan_digest": True},
            {**good, "parts": None}, {**good, "parts": [None]},
            {**good, "parts": [{"id": ""}]}, {**good, "parts": [{"id": 1}]},
            {**good, "parts": [{"id": "a"}, {"id": "a"}]},
            {**good, "project_id": "another"}, {**good, "plan_digest": "another"},
            {**good, "parts": [{"id": "another"}]},
        ]
        for bad in invalid:
            with self.subTest(document=bad):
                with self.assertRaises(ValueError):
                    compare_inspections(raw(good), raw(bad))

    def test_input_part_and_complete_output_limits(self):
        good = raw(document())
        with self.assertRaises(ValueError):
            compare_inspections(b" " * (MAX_INPUT_BYTES + 1), good)
        crowded = raw(document([{"id": str(i)} for i in range(257)]))
        with self.assertRaises(ValueError):
            compare_inspections(crowded, crowded)
        first, second = document([]), document([])
        first.update({f"k{i:05}": 0 for i in range(80000)})
        second.update({f"k{i:05}": 1 for i in range(80000)})
        left, right = raw(first), raw(second)
        self.assertLessEqual(len(left), MAX_INPUT_BYTES)
        self.assertLessEqual(len(right), MAX_INPUT_BYTES)
        # A wide document remains within input limits but expanding each changed
        # field into presence/value records must meet the complete report limit.
        with self.assertRaisesRegex(ValueError, "8 MiB report"):
            compare_inspections(left, right)

    def test_actual_cli_output_and_input_preservation(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            first, second, output = base/"first.json", base/"second.json", base/"report.json"
            first.write_bytes(raw(document()))
            second.write_bytes(raw(document([{"id": "audit", "state": "completed"}])))
            before = {p: (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns) for p in (first, second)}
            argv = [sys.executable, "-S", "-B", "-m", "fanout_engine.compare_inspections",
                    "--first", str(first), "--second", str(second)]
            env = {"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}
            ordinary = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True, timeout=15)
            self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
            self.assertEqual(ordinary.stderr, b"")
            expected = compare_inspections(first.read_bytes(), second.read_bytes())
            self.assertEqual(ordinary.stdout, raw(expected))
            saved = subprocess.run(argv+["--output", str(output)], cwd=ROOT, env=env,
                                   capture_output=True, timeout=15)
            self.assertEqual((saved.returncode, saved.stdout, saved.stderr), (0, b"", b""))
            self.assertEqual(output.read_bytes(), ordinary.stdout)
            for destination in (output, first, second, base):
                refused = subprocess.run(argv+["--output", str(destination)], cwd=ROOT, env=env,
                                         capture_output=True, timeout=15)
                self.assertEqual(refused.returncode, 1)
                self.assertEqual(refused.stdout, b"")
            self.assertEqual(output.read_bytes(), ordinary.stdout)
            self.assertEqual({p: (p.read_bytes(), p.stat().st_mode, p.stat().st_mtime_ns)
                              for p in (first, second)}, before)
            self.assertEqual(sorted(p.name for p in base.iterdir()), ["first.json", "report.json", "second.json"])

    def test_invalid_input_never_publishes_and_regular_referents_are_supported(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            first, second, output = base/"first.json", base/"second.json", base/"out.json"
            first.write_bytes(raw(document()))
            second.write_bytes(b"not JSON")
            with patch("sys.stderr", io.StringIO()):
                self.assertEqual(main(["--first", str(first), "--second", str(second),
                                       "--output", str(output)]), 2)
            self.assertFalse(output.exists())
            second.unlink()
            try:
                second.symlink_to(first)
            except (OSError, NotImplementedError):
                self.skipTest("host does not permit creating test symlinks")
            self.assertEqual(main(["--first", str(first), "--second", str(second),
                                   "--output", str(output)]), 0)
            self.assertTrue(json.loads(output.read_bytes())["same_input_bytes"])

    def test_absent_stdout_preserves_explicit_file_route(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            source, output = base/"saved.json", base/"out.json"
            source.write_bytes(raw(document()))
            args = ["--first", str(source), "--second", str(source)]
            stderr = io.StringIO()
            with patch("sys.stdout", None), patch("sys.stderr", stderr):
                self.assertEqual(main(args), 1)
                self.assertEqual(main(args+["--output", str(output)]), 0)
            self.assertIn("cannot write report", stderr.getvalue())
            self.assertTrue(json.loads(output.read_bytes())["same_saved_values"])


if __name__ == "__main__":
    unittest.main()
