"""Freeze authored public inputs, then observe only the published original CLI."""
from pathlib import Path
import copy
import datetime
import hashlib
import json
import os
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()

def identity(path):
    s = path.lstat()
    if not stat.S_ISREG(s.st_mode):
        raise RuntimeError("not a regular file: " + str(path))
    body = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "mode": oct(stat.S_IMODE(s.st_mode)), "mtime_ns": s.st_mtime_ns}

def write(path, body):
    with path.open("xb") as stream:
        stream.write(body)
    path.chmod(0o644)

fixtures = ROOT / "fixtures"
fixtures.mkdir()
first = {
    "project_id": "review-handoff",
    "plan_digest": "authored-declared-digest-not-authenticated",
    "capture_label": "First saved document (authored example)",
    "parts": [
        {"id": "audit", "state": "outcome_unknown", "task_id": None,
         "instruction": "Read <notes> & keep literal 雪 / مرحبا / 👩‍💻.\nNo external work is implied.",
         "confirmed": False, "attempts": 1, "zero": -0.0,
         "evidence": {"finding": "Retained unknown outcome; no retry authority.", "ordered": ["a", "b"]},
         "retired_note": None},
        {"id": "publish", "state": "queued", "depends_on": ["audit"], "note": "Hold until separately authorized."},
    ],
}
second = copy.deepcopy(first)
second["capture_label"] = "Second saved document (authored example)"
audit = second["parts"][0]
audit.update({"state": "completed", "confirmed": 0, "attempts": 1.0, "zero": 0.0,
              "artifact_ref": None, "task_id": "recorded-local-reference",
              "evidence": {"finding": "A changed saved claim only: <script>literal</script>\u202e", "ordered": ["b", "a"]}})
del audit["retired_note"]
second["parts"].reverse()
first_bytes = encoded(first)
second_bytes = (json.dumps(second, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
write(fixtures / "first.json", first_bytes)
write(fixtures / "second.json", second_bytes)
order_only = copy.deepcopy(first)
order_only["parts"].reverse()
write(fixtures / "order-only.json", encoded(order_only))
write(fixtures / "occupied.html", b"Existing recipient file must survive.\n")

def side(document, field):
    return {"present": True, "value": document[field]} if field in document else {"present": False}

# Field names are independently enumerated here; this fixture producer does not
# import the original comparator or any later renderer.
changed_fields = ["artifact_ref", "attempts", "confirmed", "evidence", "retired_note", "state", "task_id", "zero"]
expected = {
    "schema": "fanout.saved-inspection-comparison/1", "saved_data_only": True,
    "first": {"input_bytes": len(first_bytes), "input_sha256": hashlib.sha256(first_bytes).hexdigest(), "document": first},
    "second": {"input_bytes": len(second_bytes), "input_sha256": hashlib.sha256(second_bytes).hexdigest(), "document": second},
    "same_input_bytes": False, "same_saved_values": False, "part_order_changed": True,
    "top_level_changes": [{"field": "capture_label", "first": side(first, "capture_label"), "second": side(second, "capture_label")}],
    "changed_part_ids": ["audit"],
    "part_changes": [{"part_id": "audit", "fields": [{"field": f, "first": side(first["parts"][0], f), "second": side(second["parts"][1], f)} for f in changed_fields]}],
}
write(fixtures / "expected-comparison.json", encoded(expected))
expectations = {
    "schema": "hamon.loom.saved-inspection-html-public-fixtures.v1",
    "origin": "Authored saved-document examples, not captured live-ledger observations or real task outcomes. No native plan/digest authentication is claimed.",
    "baseline": "a64d8e08bd9db201931ab105caa848e06d5668b2",
    "contract": "https://github.com/Jacob-Met/multi-agent-fanout-engine/pull/95#issuecomment-6153711131",
    "candidate_authored": False,
    "expected_changed_part_ids": ["audit"], "expected_fields": changed_fields,
    "top_level_fields": ["capture_label"],
    "order_only": "Same saved fields and no field changes, but first/second part array order differs; part_order_changed true and same_saved_values false.",
    "display": ["Complete first/second present/value envelopes", "Missing distinct from explicit null", "False distinct from integer 0", "Integer 1 distinct from float 1.0", "Negative floating zero distinct from positive zero", "Literal markup, ordinary Unicode, newline and bidi formatting remain text", "Complete original native JSON+LF download", "First/second labels do not imply chronology", "Both full parsed documents remain available"],
    "layout": "Readable desktop comparison with wrapped complete field values; native collapsible complete documents; no scripts or external resources.",
    "preservation": "Default native JSON unchanged; no input/source/occupied destination mutation. Complete native admission precedes rendering and publication.",
}
write(fixtures / "expectations.json", encoded(expectations))
protected = sorted(p for p in ROOT.rglob("*") if p.is_file())
before = [identity(p) for p in protected]
freeze = {"schema": "hamon.loom.saved-inspection-html-original-freeze.v1", "frozen_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "candidate_exists": (ROOT / "candidate").exists(), "inputs": before}
assert freeze["candidate_exists"] is False
write(ROOT / "original-freeze-v1.json", encoded(freeze))

out = ROOT / "original-observation"
out.mkdir()
records = []
for name, extra in (("default-json", []), ("missing-html-format", ["--format", "html", "--output", str(out / "absent.html")])):
    argv = [sys.executable, "-B", "-m", "fanout_engine.compare_inspections", "--first", str(fixtures / "first.json"), "--second", str(fixtures / "second.json"), *extra]
    child = subprocess.run(argv, cwd=ROOT / "original", stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    write(out / (name + ".stdout"), child.stdout)
    write(out / (name + ".stderr"), child.stderr)
    records.append({"label": name, "argv": argv, "cwd": str(ROOT / "original"), "exit_code": child.returncode, "stdout": identity(out / (name + ".stdout")), "stderr": identity(out / (name + ".stderr"))})
after = [identity(p) for p in protected]
checks = {
    "default_exit_0": records[0]["exit_code"] == 0,
    "default_empty_stderr": (out / "default-json.stderr").read_bytes() == b"",
    "complete_default_json_equals_independent_oracle": (out / "default-json.stdout").read_bytes() == encoded(expected),
    "missing_format_exit_2": records[1]["exit_code"] == 2,
    "missing_format_empty_stdout": (out / "missing-html-format.stdout").read_bytes() == b"",
    "missing_format_diagnostic": b"unrecognized arguments: --format html" in (out / "missing-html-format.stderr").read_bytes(),
    "no_html_created": not (out / "absent.html").exists(),
    "all_protected_inputs_unchanged": before == after,
    "candidate_still_absent": not (ROOT / "candidate").exists(),
}
receipt = {"schema": "hamon.loom.saved-inspection-html-original-observation.v1", "accepted": all(checks.values()), "checks": checks, "commands": records, "inputs_before": before, "inputs_after": after, "python": sys.version, "executable": sys.executable, "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "scope": "Published original CLI only: successful exact native JSON and intended missing HTML format refusal. No product candidate, browser, ledger, adapter or provider operation."}
write(out / "receipt.json", encoded(receipt))
print(json.dumps({"accepted": receipt["accepted"], "checks": checks, "receipt": identity(out / "receipt.json"), "freeze": identity(ROOT / "original-freeze-v1.json"), "fixtures": [identity(p) for p in sorted(fixtures.iterdir())]}))
if not receipt["accepted"]:
    raise SystemExit(1)
