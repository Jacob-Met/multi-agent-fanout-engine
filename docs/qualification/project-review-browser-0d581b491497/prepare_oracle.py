"""Author a retained project using only the unchanged parent API."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "original"))
from fanout_engine.ledger import Ledger
from fanout_engine.plan import Part, Plan, canonical_json
from fanout_engine.inspection import inspect_project


def pin(path):
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main():
    out = ROOT / "oracle"
    out.mkdir()
    literal = "Literal <b>bold?</b> & quotes \" ' — 雪 λ\nSecond line\tTAB\x01\x7f\x85"
    parts = [
        Part("z_ready", literal, (), ("zeta", "alpha", "zeta")),
        Part("a_blocked", "Wait on failed and unknown; completed is cut.",
             ("b_failed", "u_unknown", "m_complete")),
        Part("m_complete", "Receive the exact artifact, with retained evidence."),
        Part("b_failed", "Keep the observed failure; do not schedule a retry."),
        Part("u_unknown", "Retain an unknown external outcome."),
        Part("r_running", "Keep the real task reference and route."),
        Part("d_dispatching", "No acceptance was recorded; this remains dispatching."),
        Part("c_ready_child", "Direct dependency is completed.", ("m_complete",)),
    ]
    plan = Plan("browser-review", tuple(parts))
    database = out / "authored # % λ.sqlite3"
    evidence = {
        "source": "authored consumer receipt 雪",
        "locator": "https://example.invalid/retained?<b>literal</b>&x=1",
        "finding": "Literal <em>evidence</em>\nControl \x02 and a long token: " + "W" * 160,
    }
    route = {"model": "observed-model", "reasoning_effort": "high"}
    with Ledger(str(database)) as ledger:
        ledger.record_plan(plan)
        for part_id in ["m_complete", "b_failed", "u_unknown", "r_running", "d_dispatching"]:
            ledger.mark_dispatching(plan.project_id, part_id, "worker 雪 # %", route)
            if part_id != "d_dispatching":
                ledger.mark_running(plan.project_id, part_id, "task λ / " + part_id)
        ledger.mark_completed(plan.project_id, "m_complete", "artifact:<b>literal</b> & 雪", evidence)
        ledger.mark_failed(plan.project_id, "b_failed", evidence)
        ledger.mark_outcome_unknown(plan.project_id, "u_unknown", evidence)
        for i, part in enumerate(parts):
            ledger._db.execute("UPDATE parts SET updated_at=? WHERE project_id=? AND part_id=?",
                               (1700000000 + i + .25, plan.project_id, part.id))
        report = inspect_project(ledger, plan.project_id)
    expected_counts = {"queued": 3, "completed": 1, "failed": 1,
                       "outcome_unknown": 1, "running": 1, "dispatching": 1}
    if report["state_counts"] != expected_counts:
        raise ValueError("hand-derived six-state counts differ")
    if report["queued_ready_ids"] != ["z_ready", "c_ready_child"]:
        raise ValueError("hand-derived ready set differs")
    if report["blocked_queued_ids"] != ["a_blocked"]:
        raise ValueError("hand-derived blocked set differs")
    if report["parts"][1]["unmet_dependencies"] != [
        {"id": "b_failed", "state": "failed"}, {"id": "u_unknown", "state": "outcome_unknown"}
    ]:
        raise ValueError("hand-derived unmet dependency order differs")
    (out / "expected.json").write_bytes((canonical_json(report) + "\n").encode("utf-8"))
    (out / "plan.json").write_bytes((canonical_json(plan.to_dict()) + "\n").encode("utf-8"))
    (out / "expectations.json").write_text(json.dumps({
        "project": plan.project_id,
        "part_order": [part.id for part in parts],
        "counts": expected_counts,
        "ready": ["z_ready", "c_ready_child"], "blocked": ["a_blocked"],
        "literal_instruction": literal,
        "evidence": evidence,
        "origin": "Unchanged parent native inspection plus separately checked hand-derived anchors.",
        "baseline_gap": "review.py is absent at the pinned parent; no original browser failure is invented.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"files": {p.name: pin(p) for p in sorted(out.iterdir())},
                      "part_count": len(parts), "counts": expected_counts}))


if __name__ == "__main__":
    main()
