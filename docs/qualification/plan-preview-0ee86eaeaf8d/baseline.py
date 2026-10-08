#!/usr/bin/env python3
"""Receive existing plan/router APIs and the absent terminal preview route."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent


def pin(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}


def main():
    snapshot = json.loads((HERE / "baseline-source.json").read_text())
    output = HERE / "baseline-native"
    output.mkdir(exist_ok=False)
    plan = {"project": "authored-review", "parts": [
        {"id": "review", "instruction": "Review the completed draft against its sources.", "depends_on": ["draft"], "tags": ["review"]},
        {"id": "draft", "instruction": "Write a short source-bound draft.", "depends_on": ["research"]},
        {"id": "research", "instruction": "Read the authored source 日本語 fixture.", "tags": ["sources"]},
        {"id": "notes", "instruction": "Prepare a separate empty notes template."},
        {"id": "handoff", "instruction": "Prepare an offline handoff after both prerequisites.", "depends_on": ["review", "notes"]},
    ]}
    routes = {
        "catalog": {"model-a": ["low", "high"], "model-b": ["low", "high"]},
        "pool": [{"model": "model-a", "effort": "low"}, {"model": "model-b", "effort": "low"}],
        "explicit_routes": {"review": {"model": "model-b", "effort": "high"}},
        "step_up": {"model": "model-b", "effort": "high"},
    }
    api_code = r'''
import dataclasses, json, pathlib, sys
side_effect_events = []
def audit(event, args):
    if event.startswith(('sqlite3.connect', 'socket.', 'subprocess.Popen')):
        side_effect_events.append(event)
sys.addaudithook(audit)
from fanout_engine import Plan, Route, EffortRouter, strict_json_loads
plan = Plan.from_dict(strict_json_loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8')))
settings = strict_json_loads(pathlib.Path(sys.argv[2]).read_text(encoding='utf-8'))
router = EffortRouter(settings['catalog'], pool=[Route(**row) for row in settings['pool']], step_up=Route(**settings['step_up']))
rows = []
for part in plan.parts:
    explicit = settings['explicit_routes'].get(part.id)
    route = router.route_for(part.id, Route(**explicit) if explicit is not None else None)
    rows.append({'part_id': part.id, 'route': dataclasses.asdict(route), 'idempotency_key': plan.idempotency_key(part.id)})
print(json.dumps({'native_plan': plan.to_dict(), 'native_plan_digest': plan.digest,
    'dependency_ready_without_completions': [part.id for part in plan.ready_parts()],
    'native_routes': rows, 'declared_step_up': dataclasses.asdict(router.step_up),
    'observed_connection_or_spawn_events': side_effect_events}, ensure_ascii=False, indent=2))
assert not side_effect_events
'''
    with tempfile.TemporaryDirectory(prefix="fanout-preview-0ee86-", dir="/dev") as temporary:
        root = Path(temporary)
        source = root / "source"
        for row in snapshot["files"]:
            data = row["content"].encode()
            assert pin(data)["git_blob"] == row["sha"]
            target = source / row["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        plan_file, routes_file = root / "plan.json", root / "routes.json"
        for filename, value in [(plan_file, plan), (routes_file, routes)]:
            data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()
            filename.write_bytes(data)
            (output / filename.name).write_bytes(data)
        prior = root / "existing-preview.json"
        prior.write_bytes(b'{"retained":"prior user output"}\n')
        before = {str(p.relative_to(root)): pin(p.read_bytes()) for p in root.rglob("*") if p.is_file()}
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        runs = []

        def invoke(label, argv, category):
            result = subprocess.run(argv, cwd=source, env=env, capture_output=True, timeout=10)
            (output / (label + ".stdout.txt")).write_bytes(result.stdout)
            (output / (label + ".stderr.txt")).write_bytes(result.stderr)
            runs.append({"label": label, "category": category, "argv": argv, "cwd": str(source), "returncode": result.returncode,
                         "stdout": pin(result.stdout), "stderr": pin(result.stderr)})
            return result

        native = invoke("01-native-plan-routing", [sys.executable, "-B", "-c", api_code, str(plan_file), str(routes_file)], "Existing public Python APIs; no Ledger or Hub instance")
        assert native.returncode == 0, native.stderr.decode()
        report = json.loads(native.stdout)
        assert report["native_plan"] == {"project": plan["project"], "parts": [dict(id=row["id"], instruction=row["instruction"], depends_on=row.get("depends_on", []), tags=row.get("tags", [])) for row in plan["parts"]]}
        assert report["dependency_ready_without_completions"] == ["research", "notes"]
        assert len(report["native_routes"]) == 5
        assert report["native_routes"][0]["route"] == {"model": "model-b", "effort": "high"}
        assert len({row["idempotency_key"] for row in report["native_routes"]}) == 5
        assert report["observed_connection_or_spawn_events"] == []
        absent = invoke("02-missing-preview-command", [sys.executable, "-B", "-m", "fanout_engine.preview", "--plan", str(plan_file), "--routes", str(routes_file), "--output", str(prior)], "Absent maintained terminal consumer")
        assert absent.returncode != 0
        assert b"No module named fanout_engine.preview" in absent.stderr
        after = {str(p.relative_to(root)): pin(p.read_bytes()) for p in root.rglob("*") if p.is_file()}
        assert before == after
        receipt = {"repository": snapshot["repository"], "base": snapshot["base"], "tree": snapshot["tree"],
                   "runtime": {"python": sys.executable, "version": sys.version, "platform": sys.platform},
                   "product_processes": 2, "existing_api_processes": 1, "absent_cli_processes": 1,
                   "observed_native_output": report, "processes": runs, "before": before, "after": after,
                   "all_source_input_and_prior_output_bytes_preserved": True,
                   "scope": "Authored-plan and caller-supplied route preview before Ledger/Hub use. This is not the separately owned retained-project inspection workflow.",
                   "boundaries": ["Synthetic local plan and model identifiers only.", "No Ledger or Hub instance, dispatch, provider, broker, host or account operation.", "Initial dependency readiness is not queued/runtime dispatch eligibility.", "The missing module establishes an absent terminal route, not a failed worker submission."]}
        (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"receipt": str(output / "receipt.json"), "pins": pin((output / "receipt.json").read_bytes()), "native_ready": report["dependency_ready_without_completions"], "native_routes": report["native_routes"], "absent_cli_exit": absent.returncode}))


if __name__ == "__main__":
    main()
