"""Bounded final source qualification; no browser or external adapter."""
import datetime
import hashlib
import json
from pathlib import Path
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "candidate"
OUT = ROOT / "author-v1"
OUT.mkdir()

def identity(path):
    body = path.read_bytes()
    s = path.stat()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "mode": oct(stat.S_IMODE(s.st_mode)), "mtime_ns": s.st_mtime_ns}

protected = sorted(p for p in ROOT.rglob("*") if p.is_file() and OUT not in p.parents)
before = [identity(p) for p in protected]
freeze = {"schema": "hamon.loom.saved-inspection-html-author-freeze.v1", "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "sources": [identity(p) for p in sorted(SOURCE.rglob("*")) if p.is_file()], "inputs": before, "base_commit": "a64d8e08bd9db201931ab105caa848e06d5668b2"}
(OUT / "freeze.json").write_text(json.dumps(freeze, sort_keys=True, indent=2) + "\n")
records = []
commands = [
    ("normal", [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_compare_inspections*.py", "-v"], SOURCE),
    ("optimized", [sys.executable, "-O", "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test_compare_inspections_html.py", "-v"], SOURCE),
]
common = ["-m", "fanout_engine.compare_inspections", "--first", str(ROOT / "fixtures/first.json"), "--second", str(ROOT / "fixtures/second.json")]
commands.extend([
    ("worked-json", [sys.executable, "-B", *common], SOURCE),
    ("worked-html", [sys.executable, "-B", *common, "--format", "html", "--output", str(OUT / "worked-comparison.html")], SOURCE),
])
for label, argv, cwd in commands:
    child = subprocess.run(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=40)
    (OUT / (label + ".stdout")).write_bytes(child.stdout)
    (OUT / (label + ".stderr")).write_bytes(child.stderr)
    records.append({"label": label, "argv": argv, "cwd": str(cwd), "exit_code": child.returncode, "stdout": identity(OUT / (label + ".stdout")), "stderr": identity(OUT / (label + ".stderr"))})
after = [identity(p) for p in protected]
checks = {
    "all_four_commands_exit_0": all(r["exit_code"] == 0 for r in records),
    "normal_17_methods": b"Ran 17 tests" in (OUT / "normal.stderr").read_bytes(),
    "optimized_7_methods": b"Ran 7 tests" in (OUT / "optimized.stderr").read_bytes(),
    "worked_json_equals_original_and_pre_candidate_oracle": (OUT / "worked-json.stdout").read_bytes() == (ROOT / "fixtures/expected-comparison.json").read_bytes() == (ROOT / "original-observation/default-json.stdout").read_bytes(),
    "worked_html_silent_file_success": (OUT / "worked-html.stdout").read_bytes() == (OUT / "worked-html.stderr").read_bytes() == b"" and (OUT / "worked-comparison.html").is_file(),
    "selected_source_and_frozen_inputs_exact": before == after,
}
receipt = {"schema": "hamon.loom.saved-inspection-html-author-receipt.v1", "accepted": all(checks.values()), "checks": checks, "commands": records, "inputs_before": before, "inputs_after": after, "worked_html": identity(OUT / "worked-comparison.html") if (OUT / "worked-comparison.html").is_file() else None, "python": sys.version, "finished_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "scope": "17 normal methods = 10 inherited plus 7 presentation; separate genuine optimized 7 presentation methods with optimized children. Two authored actual worked CLI outputs; no browser or live ledger/provider."}
(OUT / "receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
print(json.dumps({"accepted": receipt["accepted"], "checks": checks, "receipt": identity(OUT / "receipt.json"), "worked_html": receipt["worked_html"]}))
raise SystemExit(0 if receipt["accepted"] else 1)
