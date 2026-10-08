#!/usr/bin/env python3
"""Run the exact native consumer suite once and retain raw process evidence."""
from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest


def pin(data):
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--temp-root", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output.resolve()
    paths = sorted(p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file())
    images = {path: (source / path).read_bytes() for path in paths}
    source_before = {path: pin(data) for path, data in images.items()}
    assert "fanout_engine/preview.py" in images and "tests/test_preview.py" in images
    assert not output.exists(), "preserve previous qualification output"
    output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve durable space before any native source or test is executed.
    reservation = 512 * 1024
    try:
        with output.open("xb") as held:
            held.write(b"\0" * reservation)
            held.flush()
            os.fsync(held.fileno())
    except OSError as exc:
        print(json.dumps({
            "status": "PRE_EXECUTION_STORAGE_REFUSAL", "native_processes": 0,
            "operation": "reserve own evidence capsule", "error": repr(exc),
            "source": source_before, "partial_reservation": str(output),
        }, sort_keys=True))
        return 3

    blobs = {}
    def retain(data):
        metadata = pin(data)
        blobs.setdefault(metadata["sha256"], {
            **metadata, "base64": base64.b64encode(data).decode("ascii"),
        })
        return metadata
    def path_record(path):
        path = Path(path)
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return {"exists": False}
        record = {
            "exists": True, "mode": stat.S_IFMT(metadata.st_mode),
            "inode": metadata.st_ino, "mtime_ns": metadata.st_mtime_ns,
        }
        if stat.S_ISREG(metadata.st_mode):
            record["content"] = retain(path.read_bytes())
        elif stat.S_ISLNK(metadata.st_mode):
            record["symlink"] = os.readlink(path)
        return record

    records = []
    active_test = {"id": None}
    original_run = subprocess.run
    def recorded_run(command, *positional, **options):
        argument_paths = {}
        for flag in ("--plan", "--routes", "--output"):
            if flag in command:
                argument_paths[flag] = command[command.index(flag) + 1]
        before = {flag: path_record(path) for flag, path in argument_paths.items()}
        process = original_run(command, *positional, **options)
        raw_stdout = process.stdout
        raw_stderr = process.stderr
        records.append({
            "test": active_test["id"], "argv": [str(value) for value in command],
            "cwd": str(options.get("cwd", Path.cwd())),
            "returncode": process.returncode,
            "preexec_function": getattr(options.get("preexec_fn"), "__name__", None),
            "stdout": retain(raw_stdout) if isinstance(raw_stdout, bytes) else {
                "captured": False, "destination": str(getattr(options.get("stdout"), "name", None)),
            },
            "stderr": retain(raw_stderr) if isinstance(raw_stderr, bytes) else None,
            "before": before,
            "after": {flag: path_record(path) for flag, path in argument_paths.items()},
        })
        return process

    class Result(unittest.TextTestResult):
        def __init__(self, *arguments, **keywords):
            super().__init__(*arguments, **keywords)
            self.methods = []
            self.subtest_count = 0
        def startTest(self, test):
            active_test["id"] = test.id()
            self.methods.append(test.id())
            super().startTest(test)
        def addSubTest(self, test, subtest, err):
            self.subtest_count += 1
            super().addSubTest(test, subtest, err)

    old_cwd = Path.cwd()
    old_path = list(sys.path)
    old_tmp = tempfile.tempdir
    sys.dont_write_bytecode = True
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    log = io.StringIO()
    source_images = {path: retain(data) for path, data in images.items()}
    with tempfile.TemporaryDirectory(prefix="fanout-preview-qualification-", dir=args.temp_root) as folder:
        stage = Path(folder) / "source"
        temporary = Path(folder) / "fixtures"
        stage.mkdir()
        temporary.mkdir()
        for path, data in images.items():
            destination = stage / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        tempfile.tempdir = str(temporary)
        os.environ["TMPDIR"] = str(temporary)
        try:
            os.chdir(stage)
            sys.path.insert(0, str(stage))
            assert not any(name == "fanout_engine" or name.startswith("fanout_engine.") for name in sys.modules)
            subprocess.run = recorded_run
            suite = unittest.defaultTestLoader.discover(str(stage / "tests"), pattern="test*.py")
            result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=Result).run(suite)
            staged_after = {path: pin((stage / path).read_bytes()) for path in images}
        finally:
            subprocess.run = original_run
            os.chdir(old_cwd)
            sys.path[:] = old_path
            tempfile.tempdir = old_tmp
    origin_after = {path: pin((source / path).read_bytes()) for path in images}
    all_source_preserved = source_before == staged_after == origin_after
    receipt = {
        "repository": "Jacob-Met/multi-agent-fanout-engine",
        "base": "d65bde9c59b1d2593a80f6d838c0a40bf6768013",
        "base_tree": "d5e5ad4e316be0b20a50151f8549ac490d3d99de",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "runtime": {"executable": sys.executable, "python": sys.version, "platform": platform.platform()},
        "status": "ACCEPT" if result.wasSuccessful() and all_source_preserved else "REVISE",
        "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
        "skips": len(result.skipped), "subtests": result.subtest_count, "methods": result.methods,
        "consumer_cli_processes": len(records),
        "source_before": source_before, "staged_source_after": staged_after,
        "original_candidate_source_after": origin_after, "all_source_bytes_preserved": all_source_preserved,
        "unittest_log": retain(log.getvalue().encode("utf-8")),
        "boundary": (
            "One native run of the full candidate unittest suite; the inherited nine methods include "
            "their unchanged in-memory Ledger/local adapter controls. All recorded child processes "
            "exercise the new preview consumer; its audit control denies SQLite connections, sockets "
            "and child launches. No provider, host, private account, deployment or original baseline replay."
        ),
    }
    raw = json.dumps({
        "source_images": source_images, "processes": records, "blobs": blobs,
    }, sort_keys=True, separators=(",", ":")).encode("utf-8")
    packed = gzip.compress(raw, mtime=0)
    capsule = {
        "format": "fanout-preview-native-qualification-v1",
        "receipt": receipt,
        "raw_archive": {
            "encoding": "base64(gzip(JSON))", "decoded_json": pin(raw),
            "gzip": pin(packed), "base64": base64.b64encode(packed).decode("ascii"),
        },
    }
    encoded_capsule = (json.dumps(capsule, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if len(encoded_capsule) > reservation:
        raise RuntimeError("native capsule exceeded reserved output space; retain process output")
    with output.open("r+b") as destination:
        destination.write(encoded_capsule)
        destination.truncate()
        destination.flush()
        os.fsync(destination.fileno())
    print(json.dumps({
        "status": receipt["status"], "tests_run": result.testsRun, "subtests": result.subtest_count,
        "consumer_cli_processes": len(records), "failures": len(result.failures),
        "errors": len(result.errors), "skips": len(result.skipped),
        "source_files": len(images), "all_source_bytes_preserved": all_source_preserved,
        "capsule": {"path": str(output), **pin(encoded_capsule)},
        "unittest_log": log.getvalue(),
    }, sort_keys=True))
    return 0 if receipt["status"] == "ACCEPT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
