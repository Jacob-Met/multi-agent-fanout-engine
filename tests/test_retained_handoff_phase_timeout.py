"""Receive deadline admission and the real first phase boundary without work."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "examples" / "retained_handoff" / "run_consumer.py"


def snapshot(root):
    return {p.relative_to(root).as_posix():
            (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mode,
             p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file()}


def invoke(arguments):
    env = {key: value for key, value in os.environ.items()
           if key not in {"PYTHONPATH", "PYTHONHOME", "PYTHONOPTIMIZE", "PYTHONSTARTUP"}}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run([sys.executable, "-I", "-B", str(SCRIPT), *arguments],
                          cwd=ROOT, env=env, capture_output=True, timeout=15)


class PhaseBoundaryReached(Exception):
    """The receiving probe stopped before any real child was launched."""


class RetainedHandoffPhaseTimeoutTests(unittest.TestCase):
    def test_help_names_the_aggregate_default_and_limit(self):
        result = invoke(["--help"])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, b"")
        for text in (b"--phase-timeout-seconds", b"per child phase", b"3600",
                     b"default: 30"):
            self.assertIn(text, result.stdout)

    def test_invalid_values_refuse_before_creating_output(self):
        values = ("0", "-1", "nan", "inf", "-inf", "1e309", "1e-9999",
                  "3600.01", "", "not-a-number")
        source_before = snapshot(ROOT / "fanout_engine")
        example_before = snapshot(SCRIPT.parent)
        with tempfile.TemporaryDirectory(prefix="fanout-phase-admission-") as temporary:
            parent = Path(temporary)
            for index, value in enumerate(values):
                with self.subTest(value=value):
                    output = parent / ("refused-" + str(index))
                    result = invoke(["--output", str(output),
                                     "--phase-timeout-seconds=" + value])
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, b"")
                    self.assertIn(b"--phase-timeout-seconds", result.stderr)
                    self.assertIn(b"finite seconds greater than 0 and at most 3600",
                                  result.stderr)
                    self.assertFalse(output.exists())
            self.assertEqual(list(parent.iterdir()), [])
        self.assertEqual(snapshot(ROOT / "fanout_engine"), source_before)
        self.assertEqual(snapshot(SCRIPT.parent), example_before)

    def test_missing_value_refuses_before_creating_output(self):
        with tempfile.TemporaryDirectory(prefix="fanout-phase-missing-") as temporary:
            output = Path(temporary) / "new-run"
            result = invoke(["--output", str(output), "--phase-timeout-seconds"])
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            self.assertIn(b"--phase-timeout-seconds", result.stderr)
            self.assertIn(b"expected one argument", result.stderr)
            self.assertFalse(output.exists())

    def test_invalid_value_preserves_an_existing_destination(self):
        with tempfile.TemporaryDirectory(prefix="fanout-phase-existing-") as temporary:
            output = Path(temporary) / "occupied"
            output.mkdir()
            (output / "sentinel.txt").write_bytes(b"preserve this authored sentinel\n")
            before = snapshot(output)
            result = invoke(["--output", str(output), "--phase-timeout-seconds=nan"])
            self.assertEqual(result.returncode, 2)
            self.assertIn(b"--phase-timeout-seconds", result.stderr)
            self.assertEqual(snapshot(output), before)

    def receive_boundary(self, arguments, expected):
        source_before = snapshot(ROOT / "fanout_engine")
        example_before = snapshot(SCRIPT.parent)
        old_argv, old_path = sys.argv, list(sys.path)
        old_bytecode = sys.dont_write_bytecode
        old_cwd, old_env = os.getcwd(), dict(os.environ)
        calls = []
        with tempfile.TemporaryDirectory(prefix="fanout-phase-boundary-") as temporary:
            output = Path(temporary) / "new-run"

            def stop_before_child(command, **kwargs):
                calls.append((command, kwargs))
                raise PhaseBoundaryReached()

            try:
                sys.argv = [str(SCRIPT), "--output", str(output), *arguments]
                sys.dont_write_bytecode = True
                with patch("subprocess.run", side_effect=stop_before_child):
                    with self.assertRaises(PhaseBoundaryReached):
                        runpy.run_path(str(SCRIPT), run_name="__main__")
            finally:
                sys.argv = old_argv
                sys.path[:] = old_path
                sys.dont_write_bytecode = old_bytecode
            self.assertEqual(len(calls), 1)
            command, options = calls[0]
            self.assertEqual(command, [sys.executable, "-I", "-B", str(SCRIPT),
                                      "--phase", "start", "--output", str(output)])
            self.assertEqual(options["timeout"], expected)
            self.assertIs(type(options["timeout"]), float)
            self.assertEqual(options["cwd"], output)
            self.assertIs(options["capture_output"], True)
            self.assertEqual(sorted(p.name for p in output.iterdir()), ["source.json"])
            self.assertEqual(json.loads((output / "source.json").read_bytes())["kind"],
                             "observed-checkout-files")
        self.assertIs(sys.argv, old_argv)
        self.assertEqual(sys.path, old_path)
        self.assertIs(sys.dont_write_bytecode, old_bytecode)
        self.assertEqual(os.getcwd(), old_cwd)
        self.assertTrue(dict(os.environ) == old_env, "caller environment changed")
        self.assertEqual(snapshot(ROOT / "fanout_engine"), source_before)
        self.assertEqual(snapshot(SCRIPT.parent), example_before)

    def test_default_reaches_the_real_child_boundary_as_thirty_seconds(self):
        self.receive_boundary([], 30.0)

    def test_selected_finite_values_reach_the_real_child_boundary(self):
        for text, expected in (("180", 180.0), ("0.5", 0.5), ("3600", 3600.0)):
            with self.subTest(seconds=text):
                self.receive_boundary(["--phase-timeout-seconds", text], expected)


if __name__ == "__main__":
    unittest.main()
