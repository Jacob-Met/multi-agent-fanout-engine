"""Receive aggregate-timeout diagnostic capture without dispatching phase work."""
from __future__ import annotations

import base64
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
PARTIAL_OUT = b'{"partial":"\xe2\x82\x00'
PARTIAL_ERR = b"warning:\x00\xff\n"
SENTINEL = b"existing diagnostic must remain\n"


def snapshot(root):
    return {p.relative_to(root).as_posix():
            (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mode,
             p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file()}


class NextBoundaryReached(Exception):
    """The normal-return control stops before a second child is dispatched."""


class RetainedHandoffTimeoutOutputTests(unittest.TestCase):
    def receive(self, mode):
        before = {str(p): snapshot(p) for p in (ROOT / "fanout_engine", SCRIPT.parent)}
        old_argv, old_path = sys.argv, list(sys.path)
        old_bytecode, old_cwd, old_env = sys.dont_write_bytecode, os.getcwd(), dict(os.environ)
        real_run, real_popen = subprocess.run, subprocess.Popen
        calls, children, captured, frozen_errors = [], [], [], []
        error = None
        with tempfile.TemporaryDirectory(prefix="fanout-timeout-output-") as temporary:
            parent = Path(temporary)
            output = parent / "new-run"
            marker = parent / "controlled-child.json"

            def track_child(*args, **kwargs):
                child = real_popen(*args, **kwargs)
                children.append(child)
                return child

            def freeze_error(caught):
                captured.append(caught)
                frozen_errors.append({"command": list(caught.cmd), "timeout": caught.timeout,
                    "stdout": None if caught.stdout is None else base64.b64encode(caught.stdout).decode("ascii"),
                    "stderr": None if caught.stderr is None else base64.b64encode(caught.stderr).decode("ascii")})

            def first_boundary(command, **kwargs):
                calls.append({"command": list(command), "timeout": kwargs.get("timeout"),
                              "cwd": str(kwargs.get("cwd")),
                              "capture_output": kwargs.get("capture_output")})
                if len(calls) > 1:
                    raise NextBoundaryReached()
                if mode in ("normal", "nonzero"):
                    return subprocess.CompletedProcess(command, 0 if mode == "normal" else 7,
                                                       b'{"ordinary":true}\n', b"notice\n")
                if mode == "real":
                    code = (
                        "import json,os,pathlib,time;"
                        "pathlib.Path(" + repr(str(marker)) + ").write_text("
                        "json.dumps({'pid':os.getpid()}));"
                        "os.write(1," + repr(PARTIAL_OUT) + ");"
                        "os.write(2," + repr(PARTIAL_ERR) + ");"
                        "time.sleep(30)"
                    )
                    try:
                        with patch("subprocess.Popen", side_effect=track_child):
                            real_run([sys.executable, "-I", "-B", "-c", code], **kwargs)
                    except subprocess.TimeoutExpired as caught:
                        freeze_error(caught)
                        raise
                    raise AssertionError("Controlled child unexpectedly completed")
                if mode == "first-collision":
                    (output / "start.stdout.json").write_bytes(SENTINEL)
                elif mode == "second-collision":
                    (output / "start.stderr.log").write_bytes(SENTINEL)
                caught = subprocess.TimeoutExpired(
                    command, kwargs["timeout"],
                    output=None if mode == "absent" else PARTIAL_OUT,
                    stderr=None if mode == "absent" else PARTIAL_ERR)
                freeze_error(caught)
                raise caught

            try:
                sys.argv = [str(SCRIPT), "--output", str(output),
                            "--phase-timeout-seconds", "5"]
                sys.dont_write_bytecode = True
                with patch("subprocess.run", side_effect=first_boundary):
                    try:
                        runpy.run_path(str(SCRIPT), run_name="__main__")
                    except BaseException as caught:
                        error = caught
            finally:
                sys.argv = old_argv
                sys.path[:] = old_path
                sys.dont_write_bytecode = old_bytecode
            files = {p.relative_to(output).as_posix(): p.read_bytes()
                     for p in sorted(output.rglob("*")) if p.is_file()}
            observation = {
                "mode": mode, "calls": calls,
                "error": type(error).__name__ if error is not None else None,
                "error_text": str(error),
                "same_timeout": bool(captured and error is captured[0]),
                "timeout_is_context": bool(captured and error.__context__ is captured[0]),
                "timeout_fields_unchanged": bool(captured and
                    captured[0].timeout == 5.0 and
                    captured[0].stdout == (None if mode == "absent" else PARTIAL_OUT) and
                    captured[0].stderr == (None if mode == "absent" else PARTIAL_ERR)),
                "frozen_timeout": frozen_errors[0] if frozen_errors else None,
                "exception_fields_preserved": bool(captured and frozen_errors[0] == {
                    "command": list(captured[0].cmd), "timeout": captured[0].timeout,
                    "stdout": None if captured[0].stdout is None else base64.b64encode(captured[0].stdout).decode("ascii"),
                    "stderr": None if captured[0].stderr is None else base64.b64encode(captured[0].stderr).decode("ascii")}),
                "files": {name: {"bytes": len(data),
                          "sha256": hashlib.sha256(data).hexdigest(),
                          "base64": base64.b64encode(data).decode("ascii")}
                          for name, data in files.items()},
                "children": [{"pid": child.pid, "returncode": child.poll()}
                             for child in children],
                "marker": json.loads(marker.read_bytes()) if marker.exists() else None,
                "caller_preserved": (sys.argv is old_argv and sys.path == old_path and
                    sys.dont_write_bytecode is old_bytecode and os.getcwd() == old_cwd and
                    dict(os.environ) == old_env),
                "source_preserved": all(snapshot(Path(p)) == value
                                        for p, value in before.items()),
            }
            if not hasattr(self, "observations"):
                self.observations = []
            self.observations.append(observation)
            self.assertTrue(observation["caller_preserved"])
            self.assertTrue(observation["source_preserved"])
            self.assertTrue(all(child["returncode"] is not None
                                for child in observation["children"]))
            self.assertNotIn("receipt.json", files)
            self.assertNotIn("retained.sqlite3", files)
            self.assertNotIn("start-receipt.json", files)
            self.assertEqual(calls[0], {
                "command": [sys.executable, "-I", "-B", str(SCRIPT),
                            "--phase", "start", "--output", str(output)],
                "timeout": 5.0, "cwd": str(output), "capture_output": True})
            self.assertEqual(json.loads(files["source.json"])["kind"],
                             "observed-checkout-files")
            if captured:
                self.assertTrue(observation["exception_fields_preserved"])
            if mode != "normal":
                self.assertEqual(len(calls), 1)
            return observation, files, error, captured

    def test_real_timeout_preserves_partial_binary_bytes_and_same_exception(self):
        row, files, error, caught = self.receive("real")
        self.assertIs(error, caught[0])
        self.assertTrue(row["timeout_fields_unchanged"])
        self.assertEqual(len(row["children"]), 1)
        self.assertEqual(row["marker"]["pid"], row["children"][0]["pid"])
        self.assertEqual(files["start.stdout.json"], PARTIAL_OUT)
        self.assertEqual(files["start.stderr.log"], PARTIAL_ERR)
        self.assertEqual(sorted(files), ["source.json", "start.stderr.log", "start.stdout.json"])

    def test_absent_captures_create_empty_files_and_preserve_exception(self):
        row, files, error, caught = self.receive("absent")
        self.assertIs(error, caught[0])
        self.assertTrue(row["timeout_fields_unchanged"])
        self.assertEqual(files["start.stdout.json"], b"")
        self.assertEqual(files["start.stderr.log"], b"")

    def test_first_capture_refusal_preserves_existing_file_and_timeout_context(self):
        row, files, error, caught = self.receive("first-collision")
        self.assertIsInstance(error, FileExistsError)
        self.assertIs(error.__context__, caught[0])
        self.assertEqual(files["start.stdout.json"], SENTINEL)
        self.assertEqual(sorted(files), ["source.json", "start.stdout.json"])

    def test_second_capture_refusal_keeps_first_capture_and_timeout_context(self):
        row, files, error, caught = self.receive("second-collision")
        self.assertIsInstance(error, FileExistsError)
        self.assertIs(error.__context__, caught[0])
        self.assertEqual(files["start.stdout.json"], PARTIAL_OUT)
        self.assertEqual(files["start.stderr.log"], SENTINEL)

    def test_normal_return_streams_stay_exact_before_next_boundary(self):
        row, files, error, caught = self.receive("normal")
        self.assertIsInstance(error, NextBoundaryReached)
        self.assertEqual(caught, [])
        self.assertEqual(len(row["calls"]), 2)
        self.assertEqual(row["calls"][1]["command"][-4:-2], ["--phase", "resume"])
        self.assertEqual(files["start.stdout.json"], b'{"ordinary":true}\n')
        self.assertEqual(files["start.stderr.log"], b"notice\n")
        self.assertEqual(sorted(files), ["source.json", "start.stderr.log", "start.stdout.json"])

    def test_nonzero_return_stays_failure_with_original_streams(self):
        row, files, error, caught = self.receive("nonzero")
        self.assertIsInstance(error, RuntimeError)
        self.assertIn("start failed: notice", str(error))
        self.assertEqual(caught, [])
        self.assertEqual(files["start.stdout.json"], b'{"ordinary":true}\n')
        self.assertEqual(files["start.stderr.log"], b"notice\n")


if __name__ == "__main__":
    unittest.main()
