"""Run the frozen independent dispatch receiver on exact original/candidate inputs."""
import ast
import hashlib
import json
import pathlib
import platform
import subprocess
import sys
from datetime import datetime, timezone

root = pathlib.Path(__file__).resolve().parent
target = root / "dispatch-independent-receipt.json"
if target.exists():
    raise RuntimeError("raw receiving already exists; refusing to overwrite or repeat")
admission = json.loads((root / "source-admission.json").read_text())
checker = root / "check_dispatch_callbacks.py"
checker_before = checker.read_bytes()
source_before = {}
for profile in ("before", "candidate"):
    for relative, meta in admission["inputs"][profile]["files"].items():
        path = root / profile / relative
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != meta["sha256"]:
            raise RuntimeError("source drift before execution: " + str(path))
        source_before[str(path)] = raw

before_ast = ast.parse((root / "before/fanout_engine/dispatch.py").read_text())
candidate_ast = ast.parse((root / "candidate/fanout_engine/dispatch.py").read_text())
fn = next(n for n in candidate_ast.body if isinstance(n, ast.FunctionDef) and n.name == "dispatch_ready")
capture = fn.body.pop(1)
unchanged_ast = isinstance(capture, ast.If) and ast.dump(before_ast) == ast.dump(candidate_ast)
if not unchanged_ast:
    raise RuntimeError("source outside the one admission insertion changed")

receipt = {
    "schema": "hamon.dispatch-callback-independent-receiving.v1",
    "time_utc": datetime.now(timezone.utc).isoformat(),
    "host_platform": platform.platform(), "python": sys.version,
    "source_admission": admission,
    "checker": {"path": str(checker), "bytes": len(checker_before),
                "sha256": hashlib.sha256(checker_before).hexdigest()},
    "source_outside_admission_insertion_ast_identical": unchanged_ast,
    "runs": [],
}
for source in ("before", "candidate"):
    for optimize in (False, True):
        command = [sys.executable, "-B", "-I"]
        if optimize:
            command.append("-O")
        command += [str(checker), str(root / source)]
        run = subprocess.run(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             timeout=30, check=False)
        stdout = run.stdout.decode("utf-8")
        stderr = run.stderr.decode("utf-8")
        parsed = None
        parse_error = None
        try:
            parsed = json.loads(stdout)
        except Exception as exc:
            parse_error = {"type": type(exc).__name__, "message": str(exc)}
        receipt["runs"].append({
            "source": source, "optimize_requested": int(optimize), "command": command,
            "returncode": run.returncode, "stdout": stdout, "stderr": stderr,
            "stdout_json": parsed, "parse_error": parse_error,
        })
receipt["checker_preserved"] = checker.read_bytes() == checker_before
receipt["all_twenty_source_files_preserved"] = all(
    pathlib.Path(path).read_bytes() == original for path, original in source_before.items())
receipt["acceptance"] = {
    "original_failures_retained": all(r["returncode"] == 1 and r["stdout_json"] and
                                     r["stdout_json"]["failure_count"] > 0
                                     for r in receipt["runs"] if r["source"] == "before"),
    "candidate_profiles_pass": all(r["returncode"] == 0 and r["stdout_json"] and
                                  r["stdout_json"]["failure_count"] == 0 and
                                  r["stdout_json"]["optimize"] == r["optimize_requested"]
                                  for r in receipt["runs"] if r["source"] == "candidate"),
    "source_preserved": receipt["all_twenty_source_files_preserved"],
    "checker_preserved": receipt["checker_preserved"],
}
raw = (json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
target.write_bytes(raw)
print(json.dumps({
    "path": str(target), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
    "checker": receipt["checker"], "acceptance": receipt["acceptance"],
    "runs": [{"source": r["source"], "optimize": r["optimize_requested"], "returncode": r["returncode"],
              "cases": None if r["stdout_json"] is None else r["stdout_json"]["case_count"],
              "checks": None if r["stdout_json"] is None else r["stdout_json"]["checks"],
              "failures": None if r["stdout_json"] is None else r["stdout_json"]["failure_count"],
              "stderr": r["stderr"], "parse_error": r["parse_error"],
              "failed_cases": [] if r["stdout_json"] is None else
                  [{"name": c["name"], "count": len(c["failures"])}
                   for c in r["stdout_json"]["cases"] if c["failures"]]}
             for r in receipt["runs"]]
}, sort_keys=True))
raise SystemExit(0 if all(receipt["acceptance"].values()) else 2)
