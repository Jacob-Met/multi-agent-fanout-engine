"""Build the frozen PR54 source/evidence ZIP from immutable Git objects."""
from __future__ import annotations

import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
import zipfile

REPO = Path("/private/tmp/hamon-estate-plan-current-main-37ede-20261013")
OUTPUT = Path("/private/tmp/hamon-estate-fanout-kit-37ede-20261013")
COMMIT = "000b1a0927b3864befb75f791f793991f5b53b5e"
TREE = "35472226a5fe2b208e1fcee8d19efe49fe3e5fbf"
PRODUCT_COMMIT = "de72b62cac3f2d783691b7dfe39800e658b0800b"
PRODUCT_TREE = "7579c83e1dcc823d59b28bb19090d5d2c8e420a7"
ARCHIVE = OUTPUT / "HAMON_Fanout_Plan_Identity_37ede_000b1a0.zip"


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def identify(raw):
    return {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "git_blob": hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest(),
    }


def git(*args):
    result = subprocess.run(
        ["/usr/bin/git", *args], cwd=REPO, capture_output=True, timeout=60,
    )
    require(result.returncode == 0, result.stderr.decode(errors="replace"))
    return result.stdout


def valid_path(name):
    path = PurePosixPath(name)
    return (
        not path.is_absolute() and str(path) == name and bool(path.parts)
        and not any(part in ("", ".", "..") for part in path.parts)
        and "\\" not in name and "\0" not in name
        and ":" not in path.parts[0]
    )


def main():
    builder = Path(__file__).read_bytes()
    guide_path = OUTPUT / "README_RECEIVING.md"
    guide = guide_path.read_bytes()
    require(not ARCHIVE.exists(), "Archive exists; preserve it and inspect before rebuilding")
    git("fetch", "https://github.com/Jacob-Met/multi-agent-fanout-engine.git", COMMIT)
    require(git("rev-parse", COMMIT + "^{tree}").decode().strip() == TREE, "Source tree mismatch")
    require(git("show", "-s", "--format=%P", COMMIT).decode().split() == [PRODUCT_COMMIT],
            "Qualified source parent mismatch")
    require(git("rev-parse", PRODUCT_COMMIT + "^{tree}").decode().strip() == PRODUCT_TREE,
            "Product source tree mismatch")
    files = {}
    payloads = {}
    for row in git("ls-tree", "-rz", COMMIT).split(b"\0"):
        if not row:
            continue
        left, raw_path = row.split(b"\t", 1)
        mode, kind, blob = left.decode().split()
        name = raw_path.decode()
        require(valid_path(name), "Noncanonical repository path: " + name)
        require(kind == "blob" and mode == "100644", "Unexpected source entry mode: " + name)
        require(name not in files, "Duplicate source path")
        raw = git("cat-file", "blob", blob)
        identity = identify(raw)
        require(identity["git_blob"] == blob, "Git blob bytes mismatch: " + name)
        files[name] = dict(identity, path=name, mode=mode, origin="git")
        payloads[name] = raw
    require(len(files) == 228, "Frozen Git file count differs")
    require("README_RECEIVING.md" not in files and "MANIFEST.json" not in files,
            "Generated filename collides with source")
    files["README_RECEIVING.md"] = {
        "path": "README_RECEIVING.md", "bytes": len(guide),
        "sha256": hashlib.sha256(guide).hexdigest(), "mode": "100644",
        "origin": "generated",
    }
    payloads["README_RECEIVING.md"] = guide
    require(len({name.casefold() for name in [*files, "MANIFEST.json"]}) == 230,
            "Portable path collision")
    manifest = {
        "schema": "hamon.fanout-plan-identity-kit.manifest.v1",
        "repository": "Jacob-Met/multi-agent-fanout-engine",
        "pull_request": "https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/54",
        "source_commit": COMMIT, "source_tree": TREE,
        "product_source_commit": PRODUCT_COMMIT, "product_source_tree": PRODUCT_TREE,
        "current_main_at_qualification": "c86113dd09ff17d0c606b390b693caddb967f8b1",
        "git_file_count": 228, "payload_file_count": 229, "archive_member_count": 230,
        "layout": "Regular relative files at extraction root; no outer directory",
        "self_excluded": "MANIFEST.json",
        "files": [files[name] for name in sorted(files)],
    }
    manifest_raw = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    (OUTPUT / "MANIFEST.json").write_bytes(manifest_raw)
    payloads["MANIFEST.json"] = manifest_raw
    with zipfile.ZipFile(ARCHIVE, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(payloads):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 13, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 << 16) | 0x20
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payloads[name], compresslevel=9)
    with zipfile.ZipFile(ARCHIVE, "r") as archive:
        require(archive.namelist() == sorted(payloads), "Written member names differ")
        require(archive.testzip() is None, "ZIP CRC check failed")
        require(all(archive.read(name) == raw for name, raw in payloads.items()),
                "Written ZIP payload differs")
    require(Path(__file__).read_bytes() == builder and guide_path.read_bytes() == guide,
            "Producer input changed")
    archive_raw = ARCHIVE.read_bytes()
    receipt = {
        "schema": "hamon.fanout-plan-identity-kit.build.v1",
        "accepted": True,
        "built_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_commit": COMMIT, "source_tree": TREE,
        "product_source_commit": PRODUCT_COMMIT, "product_source_tree": PRODUCT_TREE,
        "archive": dict(identify(archive_raw), path=str(ARCHIVE)),
        "manifest": dict(identify(manifest_raw), file="MANIFEST.json"),
        "receiving_guide": dict(identify(guide), file="README_RECEIVING.md"),
        "executed_builder": dict(identify(builder), file=Path(__file__).name),
        "counts": {
            "git_files": 228, "manifest_payload_files": 229, "zip_members": 230,
            "uncompressed_bytes": sum(len(raw) for raw in payloads.values()),
        },
        "all_git_blob_identities_verified": True,
        "zip_names_crc_and_payloads_read_back_exact": True,
        "producer_inputs_unchanged": True,
        "limits": [
            "Producer assembly/readback only. No product code or test suite was executed by this builder.",
            "Independent extraction and relocated consumer receiving follow separately.",
            "The ZIP freezes the named PR54 source/evidence commit; later receipt publication does not change this archive.",
        ],
    }
    receipt_raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    (OUTPUT / "kit-build-receipt.json").write_bytes(receipt_raw)
    print(json.dumps({
        "accepted": True, "archive": receipt["archive"], "manifest": receipt["manifest"],
        "counts": receipt["counts"], "builder": receipt["executed_builder"],
        "receipt": identify(receipt_raw),
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
