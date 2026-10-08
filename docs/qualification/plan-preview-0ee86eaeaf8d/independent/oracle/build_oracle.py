#!/usr/bin/env python3
"""Freeze reference bytes using only the accepted contract and original sources."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    plan = {
        "project": "paper-preview",
        "parts": [
            {"id": "publish", "instruction": "  Assemble the 日本語 review without dispatch.  ", "depends_on": ["verify", "pack"], "tags": ["zeta", "alpha", "zeta"]},
            {"id": "scan", "instruction": "Read the authored sources."},
            {"id": "caption", "instruction": "Describe each retained figure.", "depends_on": ["scan"]},
            {"id": "verify", "instruction": "Check the descriptions.", "depends_on": ["caption"], "tags": ["review"]},
            {"id": "side", "instruction": "Keep independent notes.", "tags": ["notes", "notes"]},
            {"id": "pack", "instruction": "Collect notes and sources.", "depends_on": ["scan", "side"]},
        ],
    }
    routing = {
        "catalog": {"cpu-a": ["low", "high"], "gpu-b": ["medium"], "review-c": ["xhigh", "max"]},
        "pool": [{"model": "cpu-a", "effort": "low"}, {"model": "gpu-b", "effort": "medium"}, {"model": "cpu-a", "effort": "high"}],
        "explicit_routes": {"pack": {"model": "gpu-b", "effort": "medium"}, "publish": {"model": "review-c", "effort": "xhigh"}},
        "step_up": {"model": "review-c", "effort": "max"},
    }
    raw_plan = (json.dumps(plan, ensure_ascii=False, indent=3) + "\r\n").encode()
    raw_routes = (json.dumps(routing, ensure_ascii=False, indent=1) + "\n").encode()
    normalized = {"project": plan["project"], "parts": [
        {"id": part["id"], "instruction": part["instruction"],
         "depends_on": part.get("depends_on", []), "tags": sorted(set(part.get("tags", [])))}
        for part in plan["parts"]]}
    plan_digest = digest(canonical(normalized).encode())
    routes = []
    for part in normalized["parts"]:
        part_id = part["id"]
        index = int.from_bytes(hashlib.sha256(part_id.encode()).digest()[:8], "big") % 3
        routes.append({
            "part_id": part_id,
            "route": routing["explicit_routes"].get(part_id, routing["pool"][index]),
            "route_source": "explicit" if part_id in routing["explicit_routes"] else "pool",
            "idempotency_key": "fanout-" + digest((plan["project"] + "\0" + plan_digest + "\0" + part_id).encode()),
        })
    helper = {"schema_version": 1, "plan": normalized, "plan_digest": plan_digest,
              "dependency_ready_without_completions": ["scan", "side"], "routes": routes,
              "configured_step_up": routing["step_up"]}
    cli = {**helper, "input_sha256": {"plan": digest(raw_plan), "routes": digest(raw_routes)}}
    (ROOT / "fixture-plan.json").write_bytes(raw_plan)
    (ROOT / "fixture-routes.json").write_bytes(raw_routes)
    (ROOT / "expected.json").write_bytes((json.dumps({"helper": helper, "cli": cli}, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode())
    (ROOT / "expected-stdout.json").write_bytes((canonical(cli) + "\n").encode())
    print(json.dumps({"parts": 6, "plan_digest": plan_digest, "readiness": ["scan", "side"],
                      "expected_stdout_sha256": digest((ROOT / "expected-stdout.json").read_bytes()),
                      "original_or_candidate_product_processes": 0}))


if __name__ == "__main__":
    main()
