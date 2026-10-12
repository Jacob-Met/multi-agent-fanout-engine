"""Independent persisted-identity receiving of frozen ledger sources."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import types

REPO = Path("/private/tmp/hamon-estate-ledger-worker1-20261012-37ede76e")
BASE = "dca36bef09f39a2b339cc116051b5784619f71ee"
HEAD = "82816fffa823a605f1d54d4bbc091c2a26447afb"
PIN = "2ad8ad98de472a8deeaf6b0e656e868b906cbdc855912374aa456998797e5b14"
OUT = Path(__file__).parent
RUN = OUT / ("course-" + str(sys.flags.optimize))
RUN.mkdir()
def source(ref, path):
    return subprocess.check_output(["git", "-C", str(REPO), "show", ref + ":" + path])
before = source(BASE, "fanout_engine/ledger.py")
after = source(HEAD, "fanout_engine/ledger.py")
plan_source = source(HEAD, "fanout_engine/plan.py")
if hashlib.sha256(after).hexdigest() != PIN:
    raise SystemExit("candidate source mismatch")
if plan_source != source(BASE, "fanout_engine/plan.py"):
    raise SystemExit("plan dependency changed")
native_path = REPO / "fanout_engine/ledger.py"
native_before = native_path.read_bytes()
if native_before != after:
    raise SystemExit("candidate checkout source differs from frozen commit")
package = types.ModuleType("received_ledger")
package.__path__ = []
sys.modules[package.__name__] = package
def load(name, raw):
    module = types.ModuleType(name)
    module.__package__ = "received_ledger"
    sys.modules[name] = module
    exec(compile(raw, name, "exec"), module.__dict__)
    return module
pm = load("received_ledger.plan", plan_source)
versions = {
    "original": load("received_ledger.original", before),
    "candidate": load("received_ledger.candidate", after),
}
Plan, Part, canonical_json = pm.Plan, pm.Part, pm.canonical_json
checks, failures, observations = 0, [], []
def check(ok, label):
    global checks
    checks += 1
    if not ok:
        failures.append(label)
class MutablePart:
    def __init__(self):
        self.id, self.instruction = "task", "retain validated instruction"
        self.depends_on, self.tags = ["b", "a"], ["zeta", "alpha", "zeta"]
    def to_dict(self):
        return {"id": self.id, "instruction": self.instruction,
                "depends_on": list(self.depends_on), "tags": list(self.tags)}
class CombinedCustomPlan(Plan):
    def to_dict(self):
        document = super().to_dict()
        document["parts"] = list(reversed(document["parts"]))
        return document
    def idempotency_key(self, part_id):
        return "receiver-namespace:" + super().idempotency_key(part_id)
def make(cls=Plan):
    mutable = MutablePart()
    return cls("receiver-project", (Part("a", "first"), Part("b", "second"), mutable)), mutable
def expected(plan):
    return {"document": canonical_json(plan.to_dict()), "digest": plan.digest,
            "payloads": {p.id: canonical_json(p.to_dict()) for p in plan.parts},
            "keys": {p.id: plan.idempotency_key(p.id) for p in plan.parts}}
def identity(snapshot):
    return {"document": snapshot["plan_json"], "digest": snapshot["plan_digest"],
            "payloads": {p["part_id"]: p["payload_json"] for p in snapshot["parts"]},
            "keys": {p["part_id"]: p["idempotency_key"] for p in snapshot["parts"]}}
stable_records = {}
for version, module in versions.items():
    for label, cls in (("native", Plan), ("combined-subclass", CombinedCustomPlan)):
        plan, mutable = make(cls)
        want = expected(plan)
        database = RUN / (version + "-" + label + ".sqlite")
        ledger = module.Ledger(str(database))
        check(ledger.record_plan(plan) is True, version + " " + label + " initial record")
        saved = ledger.project_snapshot(plan.project_id)
        check(identity(saved) == want, version + " " + label + " exact persisted identity")
        check(all(p["payload_digest"] == plan.digest for p in saved["parts"]),
              version + " " + label + " payload digest")
        previous_bytes = database.read_bytes()
        previous_events = ledger.events(plan.project_id)
        check(ledger.record_plan(plan) is False, version + " " + label + " repeated record")
        check(database.read_bytes() == previous_bytes, version + " " + label + " repeat bytes")
        check(ledger.events(plan.project_id) == previous_events,
              version + " " + label + " repeat events")
        ledger._db.close()
        reader = module.Ledger.open_readonly(database)
        reopened = identity(reader.project_snapshot(plan.project_id))
        check(reopened == want, version + " " + label + " reopened identity")
        reader._db.close()
        stable_records[(version, label)] = reopened
    plan, mutable = make()
    database = RUN / (version + "-stale.sqlite")
    ledger = module.Ledger(str(database))
    statements = []
    ledger._db.set_trace_callback(statements.append)
    unchanged_db = database.read_bytes()
    validated_digest = plan.digest
    mutable.instruction = "changed before admission"
    mutable.tags.append("newtag")
    changed_input = canonical_json(plan.to_dict())
    error = None
    try:
        accepted = ledger.record_plan(plan)
    except Exception as exc:
        accepted, error = None, type(exc).__name__ + ": " + str(exc)
    if version == "original":
        record = ledger.project_snapshot(plan.project_id)
        check(accepted is True and record["plan_digest"] == validated_digest,
              "original stale control admitted earlier identity")
        check(hashlib.sha256(record["plan_json"].encode()).hexdigest() != record["plan_digest"],
              "original stale control remains discriminating")
    else:
        check(error is not None and error.startswith("LedgerError:"),
              "candidate stale source rejected")
        check(not any(s.startswith("BEGIN") for s in statements),
              "candidate refuses before opening transaction")
        check(ledger.project_snapshot(plan.project_id) is None, "candidate stale no project")
        check(ledger.events(plan.project_id) == [], "candidate stale no events")
        check(database.read_bytes() == unchanged_db, "candidate stale database bytes unchanged")
        check(canonical_json(plan.to_dict()) == changed_input, "candidate stale caller data unchanged")
    observations.append({"version": version, "case": "stale-before-admission",
                         "accepted": accepted, "error": error})
    ledger._db.close()

    plan, mutable = make()
    want = expected(plan)
    database = RUN / (version + "-transaction-callback.sqlite")
    ledger = module.Ledger(str(database))
    fired = []
    def mutate(sql):
        if sql == "BEGIN IMMEDIATE" and not fired:
            fired.append(sql)
            mutable.instruction = "changed during transaction callback"
            mutable.depends_on.clear()
            mutable.tags.reverse()
            mutable.tags.append("callbacktag")
    ledger._db.set_trace_callback(mutate)
    check(ledger.record_plan(plan) is True, version + " callback record completes")
    ledger._db.set_trace_callback(None)
    snapshot = ledger.project_snapshot(plan.project_id)
    got = identity(snapshot)
    check(len(fired) == 1, version + " real BEGIN callback fired")
    check(got["document"] == want["document"], version + " document captured before BEGIN")
    if version == "original":
        check(got["payloads"] != want["payloads"], "original callback inconsistent payload witness")
    else:
        check(got == want, "candidate all persisted identity uses detached capture")
        check(json.loads(got["payloads"]["task"])["tags"] == ["zeta", "alpha", "zeta"],
              "candidate native repeated tags/order retained")
        check(json.loads(got["payloads"]["task"])["depends_on"] == ["b", "a"],
              "candidate authored dependency order retained")
    ledger._db.close()
    reader = module.Ledger.open_readonly(database)
    check(identity(reader.project_snapshot(plan.project_id)) == got,
          version + " callback record exact after read-only reopen")
    reader._db.close()
    observations.append({"version": version, "case": "BEGIN-callback",
                         "detached_identity": got == want,
                         "document_matches_validated": got["document"] == want["document"]})
for label in ("native", "combined-subclass"):
    check(stable_records[("original", label)] == stable_records[("candidate", label)],
          label + " entire persisted identity unchanged from original")
check(native_path.read_bytes() == native_before, "source checkout bytes preserved")
check(source(HEAD, "fanout_engine/plan.py") == plan_source, "plan dependency bytes preserved")
result = {
    "schema": "fanout.ledger.independent-receiving.v1", "python": sys.version,
    "optimize": sys.flags.optimize, "observed_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "base_commit": BASE, "candidate_commit": HEAD,
    "source_sha256": {"original": hashlib.sha256(before).hexdigest(), "candidate": PIN,
                      "plan": hashlib.sha256(plan_source).hexdigest()},
    "checks": checks, "failures": failures, "observations": observations,
    "source_bytes_preserved": native_path.read_bytes() == native_before,
    "limit": "Standard Plan capture plus preserved subclass protocol; no post-record dispatch callback claim."
}
raw = (json.dumps(result, sort_keys=True, indent=2) + "\n").encode()
receipt = OUT / ("independent-" + str(sys.flags.optimize) + ".json")
receipt.write_bytes(raw)
print(json.dumps({"receipt": str(receipt), "bytes": len(raw),
                  "sha256": hashlib.sha256(raw).hexdigest(), "checks": checks,
                  "failures": failures, "optimize": sys.flags.optimize}, sort_keys=True))
raise SystemExit(1 if failures else 0)
