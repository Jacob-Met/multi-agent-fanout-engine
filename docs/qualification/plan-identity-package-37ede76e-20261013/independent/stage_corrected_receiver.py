import hashlib, json, shutil
from datetime import datetime, timezone
from pathlib import Path
first = Path("/private/tmp/hamon-estate-fanout-kit-receiving-37ede-20261013")
target = Path("/private/tmp/hamon-estate-fanout-kit-receiving-37ede-20261013-v2")
raw = (first / "package-receiving.json").read_bytes()
if hashlib.sha256(raw).hexdigest() != "6b0007bd558fe490bb4d3cf0bc15d46d78f8b61efffabc64c5f3de76381acbf1":
    raise RuntimeError("Original stopped receipt changed")
receipt = json.loads(raw)
if receipt["accepted"] or receipt["runs"] or receipt["error"]["message"] != "Manifest self-exclusion mismatch":
    raise RuntimeError("Unexpected predecessor")
watched = receipt["inputs_before"]
for name, expected in watched.items():
    if Path(name).name != name:
        raise RuntimeError("Nonlocal input")
    data = (first / name).read_bytes()
    if len(data) != expected["bytes"] or hashlib.sha256(data).hexdigest() != expected["sha256"]:
        raise RuntimeError("Original receiver input changed: " + name)
target.mkdir()
copied = []
for name in watched:
    if name == "receive_fanout_kit.py":
        continue
    shutil.copyfile(first / name, target / name)
    if (first / name).read_bytes() != (target / name).read_bytes():
        raise RuntimeError("Copied input differs")
    copied.append(name)
record = {
    "schema": "fanout-package-receiver-schema-correction.37ede.v1",
    "observed_at_utc": datetime.now(timezone.utc).isoformat(),
    "original_directory": str(first),
    "fresh_directory": str(target),
    "original_receipt_git_blob": "8f2ea5f710f474c296f2872b327b90311aa5a089",
    "original_receiver_git_blob": "cc54d1b26d87edcb79ba3a890c4ee598d055fbd1",
    "original_inputs_preserved": len(watched),
    "copied_inputs": copied,
    "initial_product_children_run": 0,
    "cause": "Receiver expected boolean True; published self_excluded is the filename string MANIFEST.json.",
    "correction": "Change only the receiver comparison to that published filename string.",
    "archive_or_source_changes": False,
}
path = target / "receiver-correction.json"
path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
print(json.dumps(record, indent=2, sort_keys=True))
