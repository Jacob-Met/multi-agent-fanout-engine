"""Independent receiving of the frozen fanout v2 candidate; authored state only."""
from pathlib import Path
import ast,hashlib,json,shutil,sqlite3,sys,threading,time,traceback

ROOT=Path("/dev/shm/work-portability-fanout-review-dc13ebf4687f")
BASE=Path("/dev/shm/execution-fanout-discovery-dc13ebf4687f/baseline")
CAND=Path("/dev/shm/fanout-inspection-dc13ebf4687f/candidate-v2")
MANIFEST=Path("/dev/shm/fanout-inspection-dc13ebf4687f/evidence-v2/source-manifest.json")
ORACLE=ROOT/"native-oracle.json"
DB=ROOT/"native-oracle.sqlite"
checks=[];reads=[];rejections=[];snapshots={}
def require(value,message,detail=None):
    checks.append({"name":message,"passed":bool(value),**({"detail":detail} if detail is not None else {})})
    if not value:raise AssertionError(message)
def pin(raw):
    return {"size":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
            "git_blob":hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()}
def encode(value):
    return (json.dumps(value,indent=2,ensure_ascii=False)+"\n").encode()
require(pin(ORACLE.read_bytes())["sha256"]=="01510b42676795d65a3072ad3e9876c7fcc10f2b170ecf67b645cfd277008da7","frozen native oracle pin")
oracle=json.loads(ORACLE.read_bytes());exp=oracle["expected"]
require(pin(DB.read_bytes())==oracle["database"],"original native database pin")
require(pin(MANIFEST.read_bytes())["sha256"]=="2291e1fa72dc45c343c6ecec6c47dff1dbc1fcbeb67f523db7268896c0dac7b7","candidate manifest pin")
manifest=json.loads(MANIFEST.read_bytes())
before={n:pin((CAND/n).read_bytes()) for n in manifest["candidate_files"]}
require(before==manifest["candidate_files"],"all 15 candidate inputs match author freeze")
require({n:pin((BASE/n).read_bytes()) for n in manifest["baseline_files"]}==manifest["baseline_files"],"all 12 original source inputs match")
changes=sorted(n for n,p in before.items() if manifest["baseline_files"].get(n)!=p)
require(changes==sorted(manifest["changed_paths"]),"exact six changed paths")
b=(BASE/"fanout_engine/ledger.py").read_text()
c=(CAND/"fanout_engine/ledger.py").read_text()
start=c.index("    def project_snapshot(");end=c.index("    def part_state(",start)
require(c[:start]+c[end:]==b,"removing only added snapshot method recovers every original ledger byte")
bt=ast.parse(b);ct=ast.parse(c)
bm=next(n for n in bt.body if isinstance(n,ast.ClassDef) and n.name=="Ledger")
cm=next(n for n in ct.body if isinstance(n,ast.ClassDef) and n.name=="Ledger")
oldmethods={n.name:ast.get_source_segment(b,n) for n in bm.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
newmethods={n.name:ast.get_source_segment(c,n) for n in cm.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
require(len(oldmethods)==21 and all(newmethods[k]==v for k,v in oldmethods.items()),"all 21 original Ledger methods unchanged")
require((CAND/"README.md").read_bytes().startswith((BASE/"README.md").read_bytes()),"original README bytes retained")
bi=(BASE/"fanout_engine/__init__.py").read_text()
ci=(CAND/"fanout_engine/__init__.py").read_text()
for addition in ["from .inspection import InspectionError, inspect_project\n",'    "InspectionError",\n','    "inspect_project",\n']:
    require(ci.count(addition)==1,"single additive public export "+addition.strip())
    ci=ci.replace(addition,"")
require(ci==bi,"original public initialization recovered exactly")
sys.path.insert(0,str(CAND))
from fanout_engine import Ledger,InspectionError,inspect_project
require("fanout_engine.inspection" in sys.modules and Path(sys.modules["fanout_engine.inspection"].__file__).resolve()==CAND/"fanout_engine/inspection.py","actual candidate inspector imported")
def guarded_read(ledger,label,project=exp["project_id"]):
    sql=[];denied=[];tx=ledger._db.in_transaction;changed=ledger._db.total_changes
    def authorize(action,arg1,arg2,db,source):
        if action not in (sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ):
            denied.append([action,arg1,arg2,db,source])
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    ledger._db.set_authorizer(authorize)
    ledger._db.set_trace_callback(sql.append)
    result=None;error=None
    try:result=inspect_project(ledger,project)
    except Exception as exc:error=exc
    finally:
        ledger._db.set_trace_callback(None)
        ledger._db.set_authorizer(None)
    require(not denied,label+": no write, transaction, pragma or function request",denied)
    require(len(sql)==1 and sql[0].lstrip().startswith("SELECT") and "UNION ALL" in sql[0],label+": one compound SELECT",sql)
    require(ledger._db.in_transaction==tx,label+": caller transaction state unchanged")
    require(ledger._db.total_changes==changed,label+": no database changes")
    reads.append({"name":label,"statement_count":len(sql),"error_type":type(error).__name__ if error else None,
                  "error_code":getattr(error,"code",None),"denied_actions":denied})
    return result,error
def require_report(ledger,label,project=exp["project_id"]):
    report,error=guarded_read(ledger,label,project)
    require(error is None,label+": report returned",str(error) if error else None)
    return report
states={r["part_id"]:r["state"] for r in exp["records"]}
records={r["part_id"]:r for r in exp["records"]}
expected_report={
    "project_id":exp["project_id"],"plan_digest":exp["plan_digest"],
    "state_counts":exp["state_counts"],"queued_ready_ids":exp["eligible_ids"],
    "blocked_queued_ids":[p for p in exp["queued_ids"] if exp["blockers"][p]],
    "parts":[{**part,**{k:records[part["id"]][k] for k in
              ("state","idempotency_key","worker_id","task_id","route","artifact_ref","evidence","updated_at")
              if k in records[part["id"]]},
              "route":records[part["id"]].get("route"),
              "evidence":records[part["id"]].get("evidence"),
              "unmet_dependencies":[{"id":d,"state":states[d]} for d in exp["blockers"][part["id"]]]}
             for part in exp["plan"]["parts"]],
}
with Ledger(str(DB)) as ledger:
    report=require_report(ledger,"original native oracle receiving")
    require(report==expected_report,"every reported native value, state, order and blocker matches independently frozen oracle")
    require(report["plan_digest"]!=exp["normalizing_from_dict_digest"],"direct repeated tag digest preserved")
    parts={r["id"]:r for r in report["parts"]}
    parts["done"]["route"]["extensions"]["labels"].append("caller mutation")
    parts["uncertain"]["evidence"]["extras"]["chain"][1]["literal"]="caller mutation"
    parts["blocked"]["tags"].reverse();parts["blocked"]["depends_on"].clear()
    parts["blocked"]["unmet_dependencies"][0]["state"]="caller mutation"
    report["queued_ready_ids"].clear();report["state_counts"]["queued"]=999
    snapshot=ledger.project_snapshot(exp["project_id"])
    snapshot["parts"][0]["payload_json"]="caller mutation"
    snapshot["plan_json"]="caller mutation"
    again=require_report(ledger,"after detached nested mutations")
    require(again==expected_report,"nested report and raw snapshot mutations do not change later report")
    require(ledger.events(exp["project_id"])==exp["events"],"inspection did not append or rewrite native events")
require(pin(DB.read_bytes())==oracle["database"],"original authored database bytes unchanged after receiving")
def memory_copy():
    ledger=Ledger(":memory:")
    source=sqlite3.connect("file:"+str(DB)+"?mode=ro",uri=True)
    source.backup(ledger._db);source.close()
    return ledger
ledger=memory_copy()
original_dump="\n".join(ledger._db.iterdump())
ledger._db.execute("BEGIN")
ledger._db.execute("UPDATE parts SET route_json=? WHERE project_id=? AND part_id='running'",
                   ('{"uncommitted":{"labels":["caller-owned","Ω"]}}',exp["project_id"]))
report=require_report(ledger,"inside preexisting caller transaction")
require(next(p for p in report["parts"] if p["id"]=="running")["route"]=={"uncommitted":{"labels":["caller-owned","Ω"]}},"read sees caller's prior uncommitted change")
require(ledger._db.in_transaction,"read did not commit or roll back caller transaction")
ledger._db.rollback()
require("\n".join(ledger._db.iterdump())==original_dump,"explicit caller rollback restores all authored rows")
cases=[
 ("missing expected row","DELETE FROM parts WHERE project_id=? AND part_id='queued'",(exp["project_id"],),"missing_parts"),
 ("wrong idempotency identity","UPDATE parts SET idempotency_key='wrong' WHERE project_id=? AND part_id='ready'",(exp["project_id"],),"invalid_record"),
 ("normalized payload disagrees with direct tags","UPDATE parts SET payload_json=? WHERE project_id=? AND part_id='blocked'",
  (json.dumps({**exp["plan"]["parts"][0],"tags":["alpha","zeta"]}),exp["project_id"]),"invalid_record"),
 ("non-UTF-8 decoded route","UPDATE parts SET route_json=? WHERE project_id=? AND part_id='running'",
  ('"\\ud800"',exp["project_id"]),"invalid_record"),
 ("unexpected native part","INSERT INTO parts SELECT project_id,'alien',payload_json,payload_digest,idempotency_key,state,worker_id,task_id,route_json,artifact_ref,evidence_json,updated_at FROM parts WHERE project_id=? AND part_id='ready'",(exp["project_id"],),"invalid_record"),
 ("wrong stored plan digest","UPDATE projects SET plan_digest='wrong' WHERE project_id=?",(exp["project_id"],),"invalid_record"),
]
for label,sql,args,code in cases:
    ledger._db.execute("BEGIN")
    ledger._db.execute(sql,args)
    result,error=guarded_read(ledger,label)
    require(result is None and isinstance(error,InspectionError) and error.code==code,label+": typed failure with no partial report")
    rejections.append({"name":label,"code":getattr(error,"code",None),"message":str(error)})
    require(ledger._db.in_transaction,label+": rejection did not close caller transaction")
    ledger._db.rollback()
    require("\n".join(ledger._db.iterdump())==original_dump,label+": authored rollback exact")
result,error=guarded_read(ledger,"absent literal project","Native-Oracle' OR 1=1 --")
require(result is None and isinstance(error,InspectionError) and error.code=="project_not_found","unknown literal project returns typed missing error")
rejections.append({"name":"absent literal project","code":error.code,"message":str(error)})
ledger.close()
try:inspect_project(ledger,exp["project_id"])
except Exception as exc:
    require(type(exc) is sqlite3.ProgrammingError,"ordinary closed-connection SQLite error propagates",type(exc).__name__)
else:require(False,"ordinary closed-connection SQLite error propagates")

walpath=ROOT/"concurrent-authored.sqlite"
require(not walpath.exists(),"concurrent authored destination is new")
shutil.copyfile(DB,walpath)
reader=Ledger(str(walpath))
require(reader._db.execute("PRAGMA journal_mode=WAL").fetchone()[0]=="wal","authored concurrent fixture uses WAL")
ready=threading.Event();start_writer=threading.Event();finished=threading.Event()
writer_log=[];writer_errors=[]
def writer():
    connection=None
    try:
        connection=Ledger(str(walpath))
        connection._db.execute("PRAGMA busy_timeout=1500")
        ready.set()
        if not start_writer.wait(5):raise RuntimeError("reader never reached first header row")
        evidence={"source":"independent writer fixture","locator":"fixture://commit","finding":"authored completion"}
        connection.reconcile_unknown(exp["project_id"],"uncertain",verdict="completed",
                                     evidence=evidence,artifact_ref="fixture://uncertain-complete")
        writer_log.append("uncertain reconciled completed")
        connection.mark_completed(exp["project_id"],"running","fixture://running-complete",evidence)
        writer_log.append("running completed")
    except Exception:
        writer_errors.append(traceback.format_exc())
        ready.set()
    finally:
        if connection is not None:connection.close()
        finished.set()
thread=threading.Thread(target=writer,name="authored-fanout-writer",daemon=False)
thread.start()
require(ready.wait(5),"independent writer initialized before read")
require(not writer_errors,"writer initialization succeeded",writer_errors)
held=[False]
def factory(cursor,values):
    row=sqlite3.Row(cursor,values)
    if row["record_kind"]==0 and not held[0]:
        held[0]=True
        start_writer.set()
        if not finished.wait(5):raise RuntimeError("writer did not finish while first header row held")
        if writer_errors:raise RuntimeError(writer_errors[0])
    return row
reader._db.row_factory=factory
old_report=require_report(reader,"writer commits after snapshot header fetched")
thread.join(5)
require(not thread.is_alive() and not writer_errors and len(writer_log)==2,"both native writes committed before reader continued",writer_log+writer_errors)
require(held[0] and old_report==expected_report,"one SELECT retained the complete older snapshot despite both concurrent commits")
reader._db.row_factory=sqlite3.Row
new_report=require_report(reader,"fresh read after both native commits")
require(new_report["queued_ready_ids"]==["blocked","ready","queued"],"later snapshot exposes newly eligible dependent in original order")
new_states={p["id"]:p["state"] for p in new_report["parts"]}
require(new_states["uncertain"]==new_states["running"]=="completed","later snapshot sees both completed states")
require(old_report["queued_ready_ids"]==["ready","queued"],"prior returned snapshot stays detached after commits")
reader._db.execute("BEGIN")
txn_before=require_report(reader,"explicit read transaction initial snapshot")
other=Ledger(str(walpath))
other.mark_dispatching(exp["project_id"],"queued","fixture-later",{"model":"authored","effort":"low"})
other.close()
txn_after=require_report(reader,"explicit read transaction after other connection commit")
require(txn_after==txn_before and reader._db.in_transaction,"existing read transaction snapshot retained without implicit commit")
reader._db.rollback()
fresh=require_report(reader,"read after caller ends read transaction")
require(fresh["queued_ready_ids"]==["blocked","ready"],"caller ending transaction exposes later dispatch state")
reader.close()
snapshots={"before_concurrent":expected_report,"after_two_commits":new_report,
           "after_later_dispatch":fresh,"writer_log":writer_log}
require(pin(DB.read_bytes())==oracle["database"],"frozen native database remains unchanged after all controls")
after={n:pin((CAND/n).read_bytes()) for n in manifest["candidate_files"]}
require(after==before,"all 15 frozen candidate files unchanged after review")
receipt={
    "accepted":True,"candidate_manifest":pin(MANIFEST.read_bytes()),"candidate_files":before,
    "baseline_head":manifest["baseline_head"],"baseline_tree":manifest["baseline_tree"],
    "oracle":pin(ORACLE.read_bytes()),"original_database":oracle["database"],
    "program":pin(Path(__file__).read_bytes()),"python":sys.version,"sqlite":sqlite3.sqlite_version,
    "mode":"normal; no inherited or author suite rerun","checks":checks,
    "read_calls":reads,"typed_rejections":rejections,"concurrent_observation":snapshots,
    "ordinary_sqlite_error":"ProgrammingError from closed connection propagated",
    "limits":[
      "Authored local state only; no adapter, Hub, provider, router or live ledger action.",
      "WAL concurrency uses two SQLite connections on two threads of one process; no distributed or multi-process guarantee is inferred.",
      "Caller transaction visibility is preserved; queued readiness is an observation, never a dispatch reservation.",
      "No concurrent writes through the same connection, shared-cache read_uncommitted or arbitrary row-factory contract is claimed.",
      "Existing native event history is unchanged but is not part of the new report API.",
      "No broad author/inherited suite, -O replay, original integer-limit regression replay or deployment qualification."
    ],
    "official_context":"https://sqlite.org/isolation.html (read 2026-10-08; observed controls above, not inferred outcomes)",
}
raw=encode(receipt)
with (ROOT/"review-receipt.json").open("xb") as f:f.write(raw)
print(json.dumps({"accepted":True,"checks":len(checks),"guarded_reads":len(reads),"typed_rejections":len(rejections),
 "receipt":pin(raw),"concurrent_write_log":writer_log,"sqlite":sqlite3.sqlite_version},ensure_ascii=False))

