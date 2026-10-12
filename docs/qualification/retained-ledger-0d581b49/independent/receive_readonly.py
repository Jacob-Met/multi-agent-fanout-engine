"""Independent root receiving of the saved-ledger CLI with actual SQLite."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile

SOURCE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(SOURCE))
from fanout_engine import Ledger, Part, Plan

checks = []
runs = []
def check(name, condition):
    checks.append({"name": name, "passed": bool(condition)})
    if not condition:
        raise AssertionError(name)

def cli(db, project="p"):
    flags = ["-O"] if sys.flags.optimize else []
    cmd = [sys.executable, *flags, "-B", "-m", "fanout_engine.inspect",
           "--database", str(db), "--project", project]
    run = subprocess.run(cmd, cwd=SOURCE, capture_output=True, timeout=15)
    runs.append({"argv": cmd, "returncode": run.returncode,
                 "stdout": run.stdout.decode("utf-8"), "stderr": run.stderr.decode("utf-8")})
    return run

with tempfile.TemporaryDirectory(prefix="fanout root receiving ") as work:
    root = Path(work)
    db = root / "ledger#literal?mode=rw&x=%00 café.sqlite3"
    plan = Plan("p", (Part("done", "Original source", tags=("tag", "tag")),
        Part("pending", "Uncertain dispatch"), Part("busy", "Running"),
        Part("unknown", "Uncertain outcome"), Part("failed", "Observed failure"),
        Part("ready", "Can run", depends_on=("done",)),
        Part("blocked", "Wait", depends_on=("busy", "unknown"))))
    with Ledger(str(db)) as ledger:
        ledger.record_plan(plan)
    writer = sqlite3.connect(db, isolation_level=None)
    writer.execute("UPDATE parts SET updated_at=123")
    for part, state in (("done", "completed"), ("pending", "dispatching"),
                        ("busy", "running"), ("unknown", "outcome_unknown"), ("failed", "failed")):
        writer.execute("UPDATE parts SET state=? WHERE part_id=?", (state, part))
    writer.close()
    before = db.read_bytes()
    main = cli(db)
    check("literal path reads exact file", main.returncode == 0 and not main.stderr)
    report = json.loads(main.stdout)
    check("authored part order", [p["id"] for p in report["parts"]] == [p.id for p in plan.parts])
    check("all states retained", report["state_counts"] == {"queued":2, "completed":1, "running":1,
          "dispatching":1, "outcome_unknown":1, "failed":1})
    check("direct readiness", report["queued_ready_ids"] == ["ready"] and report["blocked_queued_ids"] == ["blocked"])
    check("unmet dependency identity", report["parts"][-1]["unmet_dependencies"] ==
          [{"id":"busy", "state":"running"}, {"id":"unknown", "state":"outcome_unknown"}])
    check("repeated tags retained", report["parts"][0]["tags"] == ["tag", "tag"])
    check("complete newline output", main.stdout.endswith(b"\n") and len(main.stdout.splitlines()) == 1)
    check("main file unchanged", db.read_bytes() == before)
    with Ledger.open_readonly(db) as ledger:
        observed = []
        ledger._db.set_trace_callback(observed.append)
        try:
            ledger._db.execute("DELETE FROM parts")
        except sqlite3.OperationalError as exc:
            check("direct write refused", "readonly" in str(exc).lower())
        else:
            check("direct write refused", False)
        check("still readable after refusal", ledger.part_state("p", "ready") == "queued")
    check("database remains unchanged after write refusal", db.read_bytes() == before)
    writer = sqlite3.connect(db, isolation_level=None)
    writer.execute("PRAGMA journal_mode=WAL")
    writer.execute("PRAGMA wal_autocheckpoint=0")
    writer.execute("UPDATE parts SET updated_at=456 WHERE part_id='busy'")
    writer.execute("BEGIN IMMEDIATE")
    writer.execute("UPDATE parts SET updated_at=789 WHERE part_id='busy'")
    wal = Path(str(db) + "-wal")
    wal_before = wal.read_bytes()
    seen = cli(db)
    check("active-writer read succeeds", seen.returncode == 0)
    observed_busy = next(p for p in json.loads(seen.stdout)["parts"] if p["id"] == "busy")
    check("committed WAL visible; pending write excluded", observed_busy["updated_at"] == 456)
    check("writer transaction intact", writer.in_transaction)
    check("WAL unchanged by reader", wal.read_bytes() == wal_before)
    writer.rollback()
    writer.execute("UPDATE parts SET evidence_json='[1,]' WHERE part_id='blocked'")
    refused = cli(db)
    check("late malformed row no partial report", refused.returncode == 2 and not refused.stdout and b"invalid_record" in refused.stderr)
    writer.close()
    missing = root / "missing#name?mode=rwc.sqlite3"
    refused = cli(missing)
    check("missing literal path no create", refused.returncode == 2 and not missing.exists() and not (root/"missing").exists())
    empty = root / "empty.sqlite3"
    empty.touch()
    refused = cli(empty)
    check("empty database not initialized", refused.returncode == 2 and empty.read_bytes() == b"")
    absent = cli(db, "another")
    check("absent project distinct", absent.returncode == 3 and not absent.stdout)

out = {"passed": all(c["passed"] for c in checks), "mode": sys.flags.optimize,
       "python":sys.version, "sqlite":sqlite3.sqlite_version, "checks":checks, "runs":runs,
       "source_sha256":{str(p.relative_to(SOURCE)):hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in [SOURCE/"fanout_engine/ledger.py", SOURCE/"fanout_engine/inspect.py"]}}
print(json.dumps(out, ensure_ascii=False, indent=2))
