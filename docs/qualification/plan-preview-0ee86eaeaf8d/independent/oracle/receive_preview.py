#!/usr/bin/env python3
"""Independent actual-CLI/native-API consumer; no author tests are imported."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent


def pin(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}


def custody(path):
    stat = path.stat()
    return {**pin(path.read_bytes()), "mode": stat.st_mode, "inode": stat.st_ino, "mtime_ns": stat.st_mtime_ns}


def save(path, value):
    path.write_bytes((json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True, help="frozen preview.py; no tests or author source is modified")
    parser.add_argument("--candidate-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source_manifest = json.loads(args.original.read_bytes())
    assert source_manifest["base"] == "d65bde9c59b1d2593a80f6d838c0a40bf6768013"
    assert len(source_manifest["files"]) == 12
    original_custody = custody(args.original)
    candidate_custody = custody(args.candidate)
    assert candidate_custody["sha256"] == args.candidate_sha256
    expected = (ROOT / "expected-stdout.json").read_bytes()
    events = []
    with tempfile.TemporaryDirectory(prefix="fanout-independent-", dir=os.environ.get("HAMON_REVIEW_TMP")) as temporary:
        temp = Path(temporary)
        source = temp / "source"
        source.mkdir()
        source_pins = []
        for entry in source_manifest["files"]:
            data = entry["content"].encode()
            assert pin(data)["git_blob"] == entry["sha"]
            if entry["path"].startswith("fanout_engine/") and entry["path"].endswith(".py"):
                path = source / entry["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                source_pins.append({"path": entry["path"], **pin(data)})
        preview = source / "fanout_engine/preview.py"
        preview.write_bytes(args.candidate.read_bytes())
        source_pins.append({"path": "fanout_engine/preview.py", **pin(preview.read_bytes())})
        before_source = {p.relative_to(source).as_posix(): custody(p) for p in source.rglob("*.py")}
        environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPATH": str(source)}
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            environment.pop(name, None)

        def run_case(label, *, malformed=False, unauthorized=False, output_mode=False,
                     symlink=False, size_limit=False, full_stdout=False, api=False):
            work = temp / label
            work.mkdir()
            plan = work / "authored plan 日本語.json"
            routes = work / "routes.json"
            plan.write_bytes((ROOT / "fixture-plan.json").read_bytes())
            routes.write_bytes((ROOT / "fixture-routes.json").read_bytes())
            if malformed:
                value = json.loads(plan.read_bytes())
                value["parts"][-1]["instruction"] = " "
                plan.write_bytes(json.dumps(value, ensure_ascii=False).encode())
            if unauthorized:
                value = json.loads(routes.read_bytes())
                value["explicit_routes"]["pack"] = {"model": "review-c", "effort": "high"}
                routes.write_bytes(json.dumps(value, ensure_ascii=False).encode())
            marker = work / "retained-owner.sqlite"
            marker.write_bytes(b"unopened native owner data\n")
            destination = work / "preview.json"
            if symlink:
                destination.symlink_to(plan.name)
            before = {p.name: custody(p) for p in (plan, routes, marker)}
            names_before = sorted(p.name for p in work.iterdir())
            command = [sys.executable, "-B", "-m", "fanout_engine.preview", "--plan", str(plan), "--routes", str(routes)]
            if output_mode:
                command += ["--output", str(destination)]
            if api:
                command = [sys.executable, "-B", str(ROOT / "native_api_oracle.py"), str(ROOT)]

            def limited_write():
                signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
                resource.setrlimit(resource.RLIMIT_FSIZE, (512, 512))

            with open(os.devnull, "rb") as standard_input:
                if full_stdout:
                    with open("/dev/full", "wb", buffering=0) as standard_output:
                        completed = subprocess.run(command, cwd=work, env=environment, stdin=standard_input,
                                                   stdout=standard_output, stderr=subprocess.PIPE, timeout=20,
                                                   preexec_fn=limited_write if size_limit else None)
                    stdout = b""
                else:
                    completed = subprocess.run(command, cwd=work, env=environment, stdin=standard_input,
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20,
                                               preexec_fn=limited_write if size_limit else None)
                    stdout = completed.stdout
            after = {p.name: custody(p) for p in (plan, routes, marker)}
            actual_files = sorted(p.name for p in work.iterdir())
            actual_output = destination.read_bytes() if destination.is_file() and not destination.is_symlink() else None
            record = {"case": label, "command": command, "exit": completed.returncode,
                      "stdout_sha256": pin(stdout), "stderr_sha256": pin(completed.stderr),
                      "before": before, "after": after, "names_before": names_before, "names_after": actual_files,
                      "output": None if actual_output is None else pin(actual_output),
                      "stdout_device": "/dev/full" if full_stdout else "pipe", "file_size_limit": 512 if size_limit else None}
            (args.output / (label + ".stdout")).write_bytes(stdout)
            (args.output / (label + ".stderr")).write_bytes(completed.stderr)
            (args.output / (label + ".plan.json")).write_bytes(plan.read_bytes())
            (args.output / (label + ".routes.json")).write_bytes(routes.read_bytes())
            if actual_output is not None:
                (args.output / (label + ".output.json")).write_bytes(actual_output)
            events.append(record)
            save(args.output / "events.json", events)
            assert before == after, label + " changed input/owner bytes or metadata"
            assert before_source == {p.relative_to(source).as_posix(): custody(p) for p in source.rglob("*.py")}
            assert "Traceback" not in completed.stderr.decode("utf-8", errors="replace"), label + " emitted an uncaught failure"
            if api:
                assert completed.returncode == 0 and json.loads(stdout)["result"] == "ACCEPT"
                assert actual_files == names_before
            elif label == "stdout-success":
                assert completed.returncode == 0 and stdout == expected and completed.stderr == b""
                assert actual_files == names_before
            elif label == "file-success-no-status-write":
                assert completed.returncode == 0 and actual_output == expected and completed.stderr == b""
                assert actual_files == sorted(names_before + ["preview.json"])
            else:
                assert completed.returncode > 0 and stdout == b"" and actual_output is None
                assert actual_files == names_before, label + " left a destination or owned stage"
                if symlink:
                    assert destination.is_symlink() and os.readlink(destination) == plan.name
            record["accepted"] = True
            save(args.output / "events.json", events)

        try:
            run_case("native-api", api=True)
            run_case("stdout-success")
            run_case("file-success-no-status-write", output_mode=True, full_stdout=True)
            run_case("blocked-unauthorized-route", unauthorized=True, output_mode=True)
            run_case("malformed-later-part", malformed=True, output_mode=True)
            run_case("no-clobber-input-symlink", output_mode=True, symlink=True)
            run_case("prepublication-file-size-failure", output_mode=True, size_limit=True)
            run_case("stdout-delivery-failure", full_stdout=True)
            assert original_custody == custody(args.original)
            assert candidate_custody == custody(args.candidate)
            receipt = {"result": "ACCEPT", "runtime": sys.version, "processes": len(events),
                       "source_pins": source_pins, "original_custody": original_custody,
                       "candidate_custody": candidate_custody, "cases": events,
                       "author_tests_imported_or_executed": 0, "baseline_processes_repeated": 0,
                       "source_or_input_mutations": 0,
                       "delivery_boundary": "File-mode success remains successful with unusable stdout and publishes exact bytes without a status write. Prepublication staging failure and existing input symlink preserve prior files. Stdout failure is refusal; a general broken stream may already have delivered a prefix.",
                       "scope": "Preview only. Configured routes/catalog are not provider authorization, capacity, execution readiness or dispatch receipts."}
            save(args.output / "receipt.json", receipt)
        except BaseException as exc:
            save(args.output / "interrupted-or-failed.json", {"exception": type(exc).__name__, "message": str(exc), "events": events})
            raise
    print(json.dumps({"result": "ACCEPT", "processes": len(events), "receipt": pin((args.output / "receipt.json").read_bytes())}))


if __name__ == "__main__":
    main()
