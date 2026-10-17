"""Receive the frozen current-main fanout composition on the original native host."""
from __future__ import annotations

import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SOURCE = Path("/private/tmp/hamon-estate-plan-current-main-37ede-20261013")
OUTPUT = Path("/private/tmp/hamon-estate-plan-current-main-receiving-37ede-20261013")
PUBLISHED = "de72b62cac3f2d783691b7dfe39800e658b0800b"
NATIVE = "e5fc82c3ddb278fa60a01e320fd49bf3d59dd362"
TREE = "7579c83e1dcc823d59b28bb19090d5d2c8e420a7"
PARENTS = [
    "c86113dd09ff17d0c606b390b693caddb967f8b1",
    "d94e560f85028dca0d8798d16b377f72f562618a",
]
ADMISSION_SHA256 = "2586c9138fa714f09de739190a34490d51cd0888c4d80d004679ddd9c11fe51a"
EXPECTED_DEMO = (
    "accepted research on worker-a at model-a/low\n"
    "started: research\n"
    "waiting on prerequisites: write\n"
)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def identity(raw):
    return {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "git_blob": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
    }


def git(*args):
    completed = subprocess.run(
        ["/usr/bin/git", *args], cwd=SOURCE, capture_output=True, timeout=60,
    )
    require(
        completed.returncode == 0,
        "git command failed: " + repr(args) + " " + completed.stderr.decode(errors="replace"),
    )
    return completed.stdout.decode().strip()


def main():
    driver = Path(__file__).read_bytes()
    admission_raw = (OUTPUT / "source-admission.json").read_bytes()
    require(hashlib.sha256(admission_raw).hexdigest() == ADMISSION_SHA256,
            "Source-admission bytes differ from the frozen input")
    admission = json.loads(admission_raw)
    require(admission["native_source_commit"] == NATIVE and admission["tree"] == TREE,
            "Source-admission pin mismatch")
    require(admission["ordered_parents"] == PARENTS, "Source-admission parents mismatch")
    require(len(admission["source_files"]) == 215, "Source-admission count mismatch")
    git("fetch", "https://github.com/Jacob-Met/multi-agent-fanout-engine.git", PUBLISHED)
    require(git("rev-parse", "HEAD") == NATIVE, "Native source head moved")
    for ref in [NATIVE, PUBLISHED]:
        require(git("rev-parse", ref + "^{tree}") == TREE, "Source tree differs: " + ref)
        require(git("show", "-s", "--format=%P", ref).split() == PARENTS,
                "Ordered parents differ: " + ref)
    require(not git("diff", "--name-only", "HEAD"), "Source checkout has tracked edits")
    before = {}
    for path, expected in admission["source_files"].items():
        raw = (SOURCE / path).read_bytes()
        actual = identity(raw)
        require(actual["sha256"] == expected["sha256"] and actual["git_blob"] == expected["sha"],
                "Working source differs: " + path)
        before[path] = actual
    env = dict(os.environ)
    env.pop("PYTHONOPTIMIZE", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    records = []
    all_passed = True
    for optimized in [False, True]:
        mode = "optimized" if optimized else "normal"
        flags = ["-O", "-B"] if optimized else ["-B"]
        for label, pattern, count in [
            ("plan", "test_*_plan_*.py", 25),
            ("worker", "test_worker_identity.py", 4),
        ]:
            command = [
                sys.executable, *flags, "-m", "unittest", "discover",
                "-s", "tests", "-p", pattern, "-v",
            ]
            result = subprocess.run(command, cwd=SOURCE, env=env, capture_output=True, timeout=120)
            stdout_path = OUTPUT / (label + "-" + mode + ".stdout.txt")
            stderr_path = OUTPUT / (label + "-" + mode + ".stderr.txt")
            stdout_path.write_bytes(result.stdout)
            stderr_path.write_bytes(result.stderr)
            summary = re.search(rb"\nRan (\d+) tests? in ", result.stderr)
            observed = int(summary.group(1)) if summary else None
            accepted = (
                result.returncode == 0
                and observed == count
                and result.stderr.rstrip().endswith(b"OK")
            )
            all_passed = all_passed and accepted
            records.append({
                "name": label + "-" + mode, "command": command, "cwd": str(SOURCE),
                "returncode": result.returncode, "expected_methods": count,
                "observed_methods": observed, "accepted": accepted,
                "stdout": dict(identity(result.stdout), file=stdout_path.name),
                "stderr": dict(identity(result.stderr), file=stderr_path.name),
            })
    demo_command = [sys.executable, "-B", "examples/demo.py"]
    demo = subprocess.run(demo_command, cwd=SOURCE, env=env, capture_output=True, timeout=30)
    demo_accepted = demo.returncode == 0 and demo.stdout == EXPECTED_DEMO.encode() and demo.stderr == b""
    changed = [
        path for path, expected in before.items()
        if identity((SOURCE / path).read_bytes()) != expected
    ]
    inputs_unchanged = (
        Path(__file__).read_bytes() == driver
        and (OUTPUT / "source-admission.json").read_bytes() == admission_raw
    )
    accepted = all_passed and demo_accepted and not changed and inputs_unchanged
    receipt = {
        "schema": "hamon.plan-identity-current-main.receiving.v1",
        "received_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "accepted": accepted,
        "published_source_commit": PUBLISHED, "native_source_commit": NATIVE,
        "source_tree": TREE, "ordered_parents": PARENTS,
        "python": sys.version, "executable": sys.executable, "platform": sys.platform,
        "driver": dict(identity(driver), file=Path(__file__).name),
        "source_admission": dict(identity(admission_raw), file="source-admission.json"),
        "source_file_count": len(before), "changed_source_files": changed,
        "driver_and_admission_unchanged": inputs_unchanged,
        "courses": records,
        "demo": {
            "command": demo_command, "cwd": str(SOURCE), "returncode": demo.returncode,
            "stdout": demo.stdout.decode(), "stderr": demo.stderr.decode(),
            "accepted": demo_accepted,
        },
        "limits": [
            "Runs only the 25 maintained plan-identity/native-key and four worker-identity methods in each parent profile.",
            "This does not repeat the earlier complete 202-method course or qualify its four skipped /dev/full methods.",
            "The worker tests run their inspector children with the ordinary flags encoded in the unchanged test; no optimized inspector-child result is claimed.",
            "The demo uses the existing local adapter. No installed worker, provider call, GitHub Actions run or main integration is performed.",
        ],
    }
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    (OUTPUT / "receiving.json").write_bytes(raw)
    print(json.dumps({
        "accepted": accepted, "source": PUBLISHED, "tree": TREE,
        "courses": [{k: r[k] for k in ["name", "observed_methods", "returncode", "accepted"]} for r in records],
        "demo_accepted": demo_accepted, "source_files_preserved": len(before) - len(changed),
        "receipt": identity(raw), "directory": str(OUTPUT),
    }))
    return 0 if accepted else 1


if __name__ == "__main__":
    sys.exit(main())
