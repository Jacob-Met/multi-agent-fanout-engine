"""Freeze an independent oracle using only the original native fanout API."""
from pathlib import Path
import hashlib,json,sqlite3,sys

ROOT=Path("/dev/shm/work-portability-fanout-review-dc13ebf4687f")
BASE=Path("/dev/shm/execution-fanout-discovery-dc13ebf4687f/baseline")
PINS={
"fanout_engine/plan.py":"2bede27b5d1ce98836681befc6d5a5aeab822f62282bcc73301b3bbd2037299a",
"fanout_engine/ledger.py":"4beba942d2ce9f96e0f6e4dbc37d911db894864cd656aac4a314996277f2dcac",
"fanout_engine/dispatch.py":"120bce01120e4ad224b41fbc970b16be00262ad298bf43350a474037ebe81dcf",
}
def require(value,message):
    if not value: raise RuntimeError(message)
def pin(raw):
    return {"size":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
            "git_blob":hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()}
for rel,want in PINS.items():
    require(hashlib.sha256((BASE/rel).read_bytes()).hexdigest()==want,rel)
sys.path.insert(0,str(BASE))
from fanout_engine import Ledger,Part,Plan
require(not hasattr(__import__("fanout_engine"),"inspect_project"),"baseline unexpectedly has inspector")
dbpath=ROOT/"native-oracle.sqlite"
require(not dbpath.exists(),"authored database must be new")
plan=Plan("Native-Oracle",(
    Part("blocked",'Wait for a finding: "Ω"\nsecond line',("uncertain","done"),("zeta","alpha","zeta")),
    Part("ready","Can run after done",("done",),()),
    Part("failed","A reconciled failed native part"),
    Part("done","Completed predecessor"),
    Part("queued","Independent queued part"),
    Part("uncertain","Native uncertainty must remain visible"),
    Part("running","Accepted task remains in flight"),
    Part("dispatching","Acceptance has not been recorded"),
    Part("blocked-two","Keep failed and queued blockers in dependency order",("failed","queued"),()),
))
route={"model":"authored-Ω","effort":"low","extensions":{"labels":["one","two"],"weights":[1,2]}}
evidence={"source":"authored native API","locator":"fixture://only","finding":"known from fixture",
          "extras":{"chain":["α",{"literal":"<tag>,\"quote\"\nline"}]}}
ledger=Ledger(str(dbpath))
require(ledger.record_plan(plan) is True,"new native plan")
for part_id in ("done","failed","uncertain","running","dispatching"):
    ledger.mark_dispatching(plan.project_id,part_id,"fixture-worker",route)
    if part_id!="dispatching":
        ledger.mark_running(plan.project_id,part_id,"fixture-task-"+part_id)
ledger.mark_completed(plan.project_id,"done","fixture://Ω/output.json",evidence)
ledger.mark_outcome_unknown(plan.project_id,"uncertain",evidence)
ledger.mark_outcome_unknown(plan.project_id,"failed",evidence)
ledger.reconcile_unknown(plan.project_id,"failed",verdict="failed",evidence=evidence)
completed=ledger.completed_ids(plan.project_id)
queued=ledger.dispatchable_ids(plan.project_id)
ready={p.id for p in plan.ready_parts(completed)}
records=[ledger.part(plan.project_id,p.id) for p in plan.parts]
states=("queued","dispatching","running","outcome_unknown","completed","failed")
expected={
    "project_id":plan.project_id,"plan_digest":plan.digest,"plan":plan.to_dict(),
    "part_order":[p.id for p in plan.parts],
    "state_counts":{s:sum(r["state"]==s for r in records) for s in states},
    "dependency_ready_ids":[p.id for p in plan.parts if p.id in ready],
    "queued_ids":[p.id for p in plan.parts if p.id in queued],
    "eligible_ids":[p.id for p in plan.parts if p.id in ready and p.id in queued],
    "blockers":{p.id:[d for d in p.depends_on if d not in completed] for p in plan.parts},
    "records":records,
    "events":ledger.events(plan.project_id),
    "normalizing_from_dict_digest":Plan.from_dict(plan.to_dict()).digest,
}
require(expected["eligible_ids"]==["ready","queued"],"independent eligibility expectation")
require(expected["state_counts"]=={"queued":4,"dispatching":1,"running":1,"outcome_unknown":1,"completed":1,"failed":1},"all native states")
require(expected["normalizing_from_dict_digest"]!=plan.digest,"direct tags normalization counterexample")
ledger.close()
out={
    "oracle_source":"Original Ledger part/completed_ids/dispatchable_ids and Plan ready_parts/idempotency_key",
    "baseline_main":"d65bde9c59b1d2593a80f6d838c0a40bf6768013",
    "baseline_tree":"d5e5ad4e316be0b20a50151f8549ac490d3d99de",
    "baseline_inputs":{rel:pin((BASE/rel).read_bytes()) for rel in PINS},
    "candidate_or_author_test_code_read_before_freeze":False,
    "python":sys.version,"sqlite":sqlite3.sqlite_version,
    "database":pin(dbpath.read_bytes()),"expected":expected,
}
raw=(json.dumps(out,indent=2,ensure_ascii=False)+"\n").encode()
with (ROOT/"native-oracle.json").open("xb") as f:f.write(raw)
print(json.dumps({"oracle":pin(raw),"database":out["database"],"eligible_ids":expected["eligible_ids"],
 "state_counts":expected["state_counts"],"plan_digest":plan.digest,
 "normalizing_from_dict_digest":expected["normalizing_from_dict_digest"]},ensure_ascii=False))

