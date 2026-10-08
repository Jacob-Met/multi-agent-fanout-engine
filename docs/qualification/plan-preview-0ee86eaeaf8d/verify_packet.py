#!/usr/bin/env python3
"""Verify retained byte custody; optionally extract the exact native source image."""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve().parent
FIELDS = ("bytes", "sha256", "git_blob")


def pin(data):
    return {
        "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(),
    }


def check(data, expected):
    assert pin(data) == {key: expected[key] for key in FIELDS}, expected


def relative(name):
    value = PurePosixPath(name)
    assert name and not value.is_absolute() and ".." not in value.parts and value.parts
    return Path(*value.parts)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", type=Path, default=HERE.parents[2])
    parser.add_argument("--extract-native-source", type=Path)
    args = parser.parse_args()
    manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        check((args.repository / relative(entry["path"])).read_bytes(), entry)

    originals = json.loads((HERE / "original-twelve-files.json").read_text(encoding="utf-8"))
    assert len(originals["files"]) == 12
    for entry in originals["files"]:
        assert pin(entry["content"].encode("utf-8"))["git_blob"] == entry["sha"]
    baseline_source = json.loads((HERE / "baseline-source.json").read_text(encoding="utf-8"))
    for entry in baseline_source["files"]:
        assert pin(entry["content"].encode("utf-8"))["git_blob"] == entry["sha"]
    baseline = json.loads((HERE / "baseline-native/receipt.json").read_text(encoding="utf-8"))
    assert baseline["before"] == baseline["after"]
    for process in baseline["processes"]:
        for stream in ("stdout", "stderr"):
            check((HERE / "baseline-native" / (process["label"] + "." + stream + ".txt")).read_bytes(),
                  process[stream])

    capsule = json.loads((HERE / "author-native/capsule.json").read_text(encoding="utf-8"))
    archive = capsule["raw_archive"]
    packed = base64.b64decode(archive["base64"], validate=True)
    check(packed, archive["gzip"])
    raw = gzip.decompress(packed)
    check(raw, archive["decoded_json"])
    artifacts = json.loads(raw)
    blobs = {}
    for key, entry in artifacts["blobs"].items():
        data = base64.b64decode(entry["base64"], validate=True)
        check(data, entry)
        assert pin(data)["sha256"] == key
        blobs[key] = data
    def references(value):
        if isinstance(value, dict):
            if all(key in value for key in FIELDS):
                check(blobs[value["sha256"]], value)
            for nested in value.values():
                references(nested)
        elif isinstance(value, list):
            for nested in value:
                references(nested)
    references(artifacts["source_images"])
    references(artifacts["processes"])
    receipt = capsule["receipt"]
    assert len(artifacts["processes"]) == receipt["consumer_cli_processes"] == 41
    assert receipt["source_before"] == receipt["staged_source_after"] == receipt["original_candidate_source_after"]
    candidate = json.loads((HERE / "candidate-manifest.json").read_text(encoding="utf-8"))
    assert set(artifacts["source_images"]) == {entry["path"] for entry in candidate["files"]}
    for entry in candidate["files"]:
        image = artifacts["source_images"][entry["path"]]
        check(blobs[image["sha256"]], entry)

    independent = HERE / "independent"
    for entry in json.loads((independent / "manifest.json").read_text(encoding="utf-8"))["files"]:
        check((independent / relative(entry["path"])).read_bytes(), entry)
    oracle = independent / "oracle"
    for entry in json.loads((oracle / "oracle-manifest.json").read_text(encoding="utf-8"))["files"]:
        check((oracle / relative(entry["path"])).read_bytes(), entry)
    receiving = json.loads((independent / "native-artifacts.json").read_text(encoding="utf-8"))
    for entry in receiving["files"]:
        check(receiving["contents"][entry["sha256"]].encode("utf-8"), entry)
    assert len(receiving["files"]) == receiving["record_count"] == 35
    assert len(receiving["contents"]) == receiving["unique_body_count"] == 14

    if args.extract_native_source is not None:
        destination = args.extract_native_source
        destination.mkdir(exist_ok=False)
        for name, entry in artifacts["source_images"].items():
            path = destination / relative(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(blobs[entry["sha256"]])
    print(json.dumps({
        "status": "BYTE_CUSTODY_VERIFIED", "manifest_files": len(manifest["files"]),
        "original_source_files": len(originals["files"]),
        "candidate_source_files": len(artifacts["source_images"]),
        "author_processes": len(artifacts["processes"]),
        "author_unique_raw_bodies": len(blobs),
        "independent_artifact_records": len(receiving["files"]),
        "independent_unique_raw_bodies": len(receiving["contents"]),
        "product_or_test_execution": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
