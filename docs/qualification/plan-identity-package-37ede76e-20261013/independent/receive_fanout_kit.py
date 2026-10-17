#!/usr/bin/env python3
"""Independent package receiving with one persistent local consumer and inspect CLI."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import stat
import subprocess
import sys
import time
import traceback
import zipfile

ROOT = Path(__file__).resolve().parent
EXTRACTED = ROOT / "relocated checkout #1"
RECEIPT = ROOT / "package-receiving.json"

def utc():
    return datetime.now(timezone.utc).isoformat()

def identity(data):
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(),
    }

def file_identity(path):
    return identity(path.read_bytes())

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def matches(observed, expected, label):
    for key in ("bytes", "sha256", "git_blob"):
        if key in expected:
            require(observed[key] == expected[key], label + ": " + key)

def safe_name(name):
    require(isinstance(name, str) and name, "Empty/nontext member")
    require("\0" not in name and "\\" not in name, "Invalid path spelling")
    path = PurePosixPath(name)
    require(not path.is_absolute(), "Absolute path")
    require(all(x not in ("", ".", "..") for x in name.split("/")), "Nonliteral path")
    require(str(path) == name, "Path normalization would change a member")
    return path

receipt = {
    "schema": "fanout-kit-independent-package-receiving.37ede.v1",
    "started_at_utc": utc(),
    "accepted": False,
    "execution": {
        "device_id": "95471aa0-31a3-4fd9-a2a6-a4a06f09d7cb",
        "platform": platform.platform(),
        "python": sys.version,
        "executable": sys.executable,
        "argv": sys.argv,
        "working_directory": str(Path.cwd()),
        "scope": "Fresh package extraction, exact full Git/manifest identity, one local persistent public consumer and the maintained inspect CLI.",
        "broad_or_previous_behavior_courses_run": 0,
        "model_provider_or_remote_adapter_calls": 0,
    },
    "runs": [],
}

def run_child(name, command, cwd):
    started = utc()
    clock = time.perf_counter()
    result = subprocess.run(command, cwd=str(cwd), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=20)
    for stream, data in (("stdout", result.stdout), ("stderr", result.stderr)):
        with (ROOT / (name + "." + stream + ".txt")).open("xb") as output:
            output.write(data)
    receipt["runs"].append({
        "name": name, "command": command, "cwd": str(cwd),
        "started_at_utc": started, "finished_at_utc": utc(),
        "elapsed_seconds": time.perf_counter() - clock,
        "exit_code": result.returncode,
        "stdout": {"path": name + ".stdout.txt", **identity(result.stdout)},
        "stderr": {"path": name + ".stderr.txt", **identity(result.stderr)},
    })
    require(result.returncode == 0, name + " failed; raw streams retained")
    return result

def receive():
    require(not EXTRACTED.exists() and not RECEIPT.exists(), "Receiving outputs must be new")
    admission = json.loads((ROOT / "source-admission.json").read_text())
    require(admission["commit"] == "000b1a0927b3864befb75f791f793991f5b53b5e",
            "Wrong source commit")
    require(admission["tree"] == "35472226a5fe2b208e1fcee8d19efe49fe3e5fbf",
            "Wrong source tree")
    require(admission["git_tree_complete"], "Incomplete Git inventory")
    receipt["source"] = {key: admission[key] for key in (
        "repository", "commit", "tree", "product_commit", "git_tree_complete",
        "git_tree_entries", "manifest_git_blob", "opening_readme_git_blob"
    )}
    names = ["source-admission.json", "published-MANIFEST.json",
             "published-README_RECEIVING.md", "local_consumer.py",
             "run_inspect_cli.py", Path(__file__).name]
    watched = {name: file_identity(ROOT / name) for name in names}
    receipt["inputs_before"] = watched
    archive_path = Path(admission["archive_path"])
    archive_bytes = archive_path.read_bytes()
    archive_identity = identity(archive_bytes)
    matches(archive_identity, {"bytes": admission["archive_bytes"],
                              "sha256": admission["archive_sha256"]}, "Frozen archive")
    require(archive_identity["bytes"] == 663260, "Unexpected archive byte count")
    manifest_bytes = (ROOT / "published-MANIFEST.json").read_bytes()
    matches(identity(manifest_bytes), {
        "bytes": admission["manifest_bytes"], "sha256": admission["manifest_sha256"],
        "git_blob": admission["manifest_git_blob"]}, "Published manifest")
    readme_bytes = (ROOT / "published-README_RECEIVING.md").read_bytes()
    matches(identity(readme_bytes), {"git_blob": admission["opening_readme_git_blob"]},
            "Published opening README")
    manifest = json.loads(manifest_bytes)
    require(manifest["source_commit"] == admission["commit"]
            and manifest["source_tree"] == admission["tree"], "Manifest source mismatch")
    require(manifest["product_source_commit"] == admission["product_commit"],
            "Product source mismatch")
    require(manifest["self_excluded"] == "MANIFEST.json", "Manifest self-exclusion mismatch")
    payloads = {item["path"]: item for item in manifest["files"]}
    require(len(payloads) == len(manifest["files"]) == 229, "Manifest duplicates/count")
    git_files = {item["path"]: item for item in admission["git_files"]}
    require(len(git_files) == len(admission["git_files"]) == 228, "Git inventory duplicates/count")
    published_git = {name: item for name, item in payloads.items() if item["origin"] == "git"}
    require(set(published_git) == set(git_files), "Full Git path closure mismatch")
    require([name for name, item in payloads.items() if item["origin"] != "git"]
            == ["README_RECEIVING.md"], "Unexpected generated payload")
    for name, item in published_git.items():
        admitted = git_files[name]
        require(admitted["type"] == "blob" and admitted["mode"] == item["mode"] == "100644",
                "Unexpected Git type/mode")
        require(admitted["git_blob"] == item["git_blob"] and admitted["bytes"] == item["bytes"],
                "Git manifest metadata mismatch: " + name)
    expected_names = set(payloads) | {"MANIFEST.json"}
    entries = {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        infos = archive.infolist()
        member_names = [item.filename for item in infos]
        require(len(infos) == len(set(member_names)) == 230, "ZIP duplicates/count")
        require(set(member_names) == expected_names, "ZIP manifest closure mismatch")
        for item in infos:
            safe_name(item.filename)
            mode = (item.external_attr >> 16) & 0xFFFF
            require(not item.is_dir() and stat.S_IFMT(mode) in (0, stat.S_IFREG),
                    "Nonregular ZIP member")
            require(not (mode & 0o7000) and not (item.flag_bits & 1),
                    "Unexpected permission/encryption bits")
        require(archive.testzip() is None, "ZIP CRC failure")
        require(archive.read("MANIFEST.json") == manifest_bytes, "Manifest byte mismatch")
        require(archive.read("README_RECEIVING.md") == readme_bytes, "Opening README byte mismatch")
        for item in infos:
            data = archive.read(item.filename)
            require(len(data) == item.file_size, "ZIP file-size mismatch")
            observed = identity(data)
            if item.filename == "MANIFEST.json":
                matches(observed, identity(manifest_bytes), "Manifest")
            else:
                matches(observed, payloads[item.filename], "Payload " + item.filename)
            if item.filename in git_files:
                matches(observed, git_files[item.filename], "Git source " + item.filename)
            entries[item.filename] = {"bytes": data, "identity": observed}

    EXTRACTED.mkdir()
    for name, entry in sorted(entries.items()):
        destination = EXTRACTED.joinpath(*PurePosixPath(name).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            output.write(entry["bytes"])
        os.chmod(destination, 0o644)
    extracted_before = {
        path.relative_to(EXTRACTED).as_posix(): file_identity(path)
        for path in EXTRACTED.rglob("*") if path.is_file()
    }
    require(set(extracted_before) == expected_names, "Extracted closure mismatch")
    require(not any(path.is_symlink() for path in EXTRACTED.rglob("*")), "Extracted symlink")
    for name, observed in extracted_before.items():
        matches(observed, entries[name]["identity"], "Extracted member " + name)

    work = ROOT / "unrelated working directory"
    work.mkdir()
    outputs = ROOT / "consumer outputs"
    outputs.mkdir()
    database = outputs / "retained dispatch #1.sqlite3"
    consumer = run_child("consumer", [
        sys.executable, "-B", "-I", str(ROOT / "local_consumer.py"),
        str(EXTRACTED), str(database),
    ], work)
    outcome = json.loads(consumer.stdout)
    require(outcome["accepted"] is True and len(outcome["calls"]) == 1,
            "Persistent public consumer rejected")
    for item in outcome["imported_modules"].values():
        require(item["relative_path"] in git_files, "Consumer imported unadmitted module")
        matches(item, git_files[item["relative_path"]], "Consumer import provenance")
        require(Path(item["path"]).resolve() == (EXTRACTED / item["relative_path"]).resolve(),
                "Consumer import escaped relocated checkout")
    database_before = database.read_bytes()
    cli_provenance_path = ROOT / "inspect-provenance.json"
    inspection = run_child("inspect", [
        sys.executable, "-B", "-I", str(ROOT / "run_inspect_cli.py"),
        str(EXTRACTED), str(cli_provenance_path),
        "--database", str(database), "--project", "relocated-receiving",
    ], work)
    inspection_report = json.loads(inspection.stdout)
    require(inspection_report == outcome["report"], "CLI/native inspection reports differ")
    require(database.read_bytes() == database_before, "Inspect CLI changed database bytes")
    provenance = json.loads(cli_provenance_path.read_text())
    require(provenance["isolated"] == 1 and provenance["dont_write_bytecode"] is True,
            "Inspect profile mismatch")
    require(provenance["target"] == "fanout_engine.inspect"
            and provenance["target_git_blob"] == git_files["fanout_engine/inspect.py"]["git_blob"],
            "Wrong maintained CLI source")
    for item in provenance["imported_modules"].values():
        require(item["relative_path"] in git_files, "CLI imported unadmitted module")
        matches(item, git_files[item["relative_path"]], "CLI import provenance")
        require(Path(item["path"]).resolve() == (EXTRACTED / item["relative_path"]).resolve(),
                "CLI import escaped relocated checkout")

    extracted_after = {
        path.relative_to(EXTRACTED).as_posix(): file_identity(path)
        for path in EXTRACTED.rglob("*") if path.is_file()
    }
    require(extracted_after == extracted_before, "Package inputs changed or files were added")
    require({name: file_identity(ROOT / name) for name in watched} == watched,
            "Receiver inputs changed")
    require(file_identity(archive_path) == archive_identity, "Original archive changed")
    receipt["archive"] = {"path": str(archive_path), **archive_identity}
    receipt["manifest"] = {
        **identity(manifest_bytes), "regular_unique_relative_members": 230,
        "payloads_verified": 229, "git_files_verified": 228,
        "all_payload_sizes_sha256_and_git_blobs_match": True,
        "full_frozen_git_tree_matches": True,
        "published_manifest_and_opening_readme_byte_exact": True,
        "crc_check_passed": True,
    }
    receipt["extraction"] = {
        "path": str(EXTRACTED), "files_verified": len(extracted_after),
        "fresh_directory": True, "extra_files": [], "symlinks": [],
    }
    receipt["consumer"] = {
        "accepted": outcome["accepted"], "local_submissions": len(outcome["calls"]),
        "initial_started": outcome["first"]["started"],
        "second_started": outcome["second"]["started"],
        "not_ready": outcome["second"]["not_ready"],
        "retained_states": [[part["id"], part["state"]] for part in outcome["report"]["parts"]],
        "native_and_actual_cli_reports_equal": True,
        "database_unchanged_by_cli": True,
        "database": {"path": str(database), **identity(database_before)},
        "all_imported_modules_from_frozen_extraction": True,
        "consumer_imports": outcome["imported_modules"],
        "inspect_provenance": provenance,
    }
    receipt["preservation"] = {
        "receiver_inputs_unchanged": len(watched),
        "extracted_files_unchanged": len(extracted_after),
        "archive_unchanged": True,
    }
    receipt["accepted"] = True

try:
    receive()
except Exception as exc:
    receipt["error"] = {"type": type(exc).__name__, "message": str(exc),
                        "traceback": traceback.format_exc()}
finally:
    receipt["finished_at_utc"] = utc()
    if RECEIPT.exists():
        raise RuntimeError("Refuse to overwrite a previous package receipt")
    RECEIPT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "accepted": receipt["accepted"], "archive": receipt.get("archive"),
        "manifest": receipt.get("manifest"), "preservation": receipt.get("preservation"),
        "consumer_summary": {key: receipt.get("consumer", {}).get(key) for key in (
            "local_submissions", "initial_started", "second_started", "not_ready",
            "retained_states", "native_and_actual_cli_reports_equal",
            "database_unchanged_by_cli", "all_imported_modules_from_frozen_extraction")},
        "receipt": {"path": str(RECEIPT), **file_identity(RECEIPT)},
        "driver": {"path": str(Path(__file__)), **file_identity(Path(__file__))},
        "error": receipt.get("error"),
    }, indent=2, sort_keys=True))
sys.exit(0 if receipt["accepted"] else 1)
