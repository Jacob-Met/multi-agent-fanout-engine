"""Post-intake current Ledger withdrawal -> unchanged queued-route CLI integration."""
from __future__ import annotations
import contextlib, hashlib, json, os, pathlib, signal, sqlite3, subprocess, sys, time, traceback
sys.dont_write_bytecode=True
SOURCE=pathlib.Path(sys.argv[1]).resolve(); OUT=pathlib.Path(sys.argv[2]).resolve()
SELF=pathlib.Path(__file__).resolve(); EXPECT=SELF.with_name("withdrawal-preview-expectations-v1.json")
expected=json.loads(EXPECT.read_bytes()); OUT.mkdir()
checks=[]; commands=[]; error=None; state={}
def pin(p):
 b=p.read_bytes();s=p.stat();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),mode=s.st_mode&511,mtime_ns=s.st_mtime_ns)
def fence():
 return {str(p):pin(p) for p in [*sorted((SOURCE/"fanout_engine").glob("*.py")),SELF,EXPECT]}
def check(name,ok,**details): checks.append(dict(name=name,accepted=bool(ok),**details))
def dbfence(db): return {p.name:pin(p) for p in sorted(db.parent.glob(db.name+"*")) if p.is_file()}
def snapshot(db):
 with contextlib.closing(sqlite3.connect(db.as_uri()+"?mode=ro",uri=True)) as c:
  c.row_factory=sqlite3.Row
  return {table:[dict(x) for x in c.execute("SELECT * FROM "+table+" ORDER BY "+order)] for table,order in [("projects","project_id"),("parts","part_id"),("events","seq")]}
def group_absent(pid):
 try:os.killpg(pid,0)
 except ProcessLookupError:return True
 return False
def preview(db,routes):
 args=[sys.executable,"-B","-m","fanout_engine.queued_routes","--database",str(db),"--project",expected["project"],"--routes",str(routes)]
 p=subprocess.Popen(args,cwd=SOURCE,env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONPATH=""),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
 forced=False
 try:out,err=p.communicate(timeout=8)
 except subprocess.TimeoutExpired:
  forced=True;os.killpg(p.pid,signal.SIGTERM)
  try:out,err=p.communicate(timeout=1)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate(timeout=1)
 item=dict(arguments=args,pid=p.pid,status=p.returncode,forced=forced,group_absent=group_absent(p.pid),stdout=out.decode("utf-8","replace"),stderr=err.decode("utf-8","replace"));commands.append(item)
 return item,json.loads(item["stdout"])
before=fence()
try:
 check("Current source inputs match exact received CLI and canonical ledger pins",all(pin(SOURCE/path)["sha256"]==sha for path,sha in expected["sourcePins"].items()))
 if not checks[-1]["accepted"]:raise RuntimeError("source admission failed")
 sys.path.insert(0,str(SOURCE))
 from fanout_engine import Ledger,Plan
 plan=Plan.from_dict({"project":expected["project"],"parts":[{"id":name,"instruction":"Local fictional "+name,"depends_on":["root"] if name=="child" else []} for name in expected["partOrder"]]})
 db=OUT/"integration.sqlite3"; routes=OUT/"routes.json"
 routes.write_text(json.dumps(expected["routing"]),encoding="utf-8"); routepin=pin(routes)
 evidence=expected["evidence"]
 with Ledger(db) as ledger:
  ledger.record_plan(plan)
  for name in ["unknown","inflight"]:
   ledger.mark_dispatching(plan.project_id,name,"fictional-worker-"+name,{"model":"m","effort":"low"})
   if name=="unknown":ledger.mark_outcome_unknown(plan.project_id,name,{"source":"fixture","locator":"fixture://none","finding":"retained unknown control"})
   else:ledger.mark_running(plan.project_id,name,"fictional-task")
 initial=snapshot(db);state["beforeWithdrawal"]=initial
 def expected_report(withdrawn):
  ready=["free"] if withdrawn else ["root","free"]
  return dict(schema_version=1,project_id=plan.project_id,plan_digest=plan.digest,state_counts={"completed":0,"dispatching":0,"failed":1 if withdrawn else 0,"outcome_unknown":1,"queued":2 if withdrawn else 3,"running":1},queued_ready_ids=ready,blocked_queued_ids=["child"],parts=[{"id":name,"state":("failed" if withdrawn else "queued") if name=="root" else "outcome_unknown" if name=="unknown" else "running" if name=="inflight" else "queued","unmet_dependencies":[{"id":"root","state":"failed" if withdrawn else "queued"}] if name=="child" else []}for name in expected["partOrder"]],routes=[{"part_id":name,"route":{"model":"m","effort":"low"},"route_source":"pool","idempotency_key":plan.idempotency_key(name)}for name in ready],configured_step_up=None,routing_input_sha256=routepin["sha256"])
 f=dbfence(db);c,report=preview(db,routes)
 check("Before withdrawal actual CLI includes root and unrelated free route",c["status"]==0 and not c["stderr"] and report==expected_report(False),actual=report,expected=expected_report(False))
 check("Before preview leaves database bytes, sidecars, metadata and all SQL rows exact",f==dbfence(db) and initial==snapshot(db))
 with Ledger(db) as ledger:ledger.withdraw_queued(plan.project_id,"root",evidence)
 changed=snapshot(db);state["afterWithdrawal"]=changed
 oldrows={r["part_id"]:r for r in initial["parts"]};newrows={r["part_id"]:r for r in changed["parts"]}
 oldroot=oldrows["root"];newroot=newrows["root"]
 check("Actual API withdrawal preserves root identity and absent submission references",newroot["state"]=="failed" and json.loads(newroot["evidence_json"])==evidence and all(newroot[k]==v for k,v in oldroot.items() if k not in {"state","evidence_json","updated_at"}) and all(newroot[k] is None for k in ["worker_id","task_id","route_json","artifact_ref"]))
 check("Withdrawal appends exactly one distinct event and preserves project and other rows",changed["projects"]==initial["projects"] and changed["events"][:-1]==initial["events"] and len(changed["events"])==len(initial["events"])+1 and changed["events"][-1]["event"]=="queued_withdrawn" and changed["events"][-1]["part_id"]=="root" and json.loads(changed["events"][-1]["detail_json"])==evidence and all(newrows[k]==v for k,v in oldrows.items() if k!="root"))
 f=dbfence(db);c,report=preview(db,routes)
 check("Reopened actual CLI excludes withdrawn root, blocks child and preserves free route",c["status"]==0 and not c["stderr"] and report==expected_report(True),actual=report,expected=expected_report(True))
 check("After preview leaves database bytes, sidecars, metadata and all SQL rows exact",f==dbfence(db) and changed==snapshot(db))
 check("Unknown and running identities remain exact and unrouted",all(oldrows[k]==newrows[k] for k in ["unknown","inflight"]) and all(r["part_id"] not in {"unknown","inflight"} for r in report["routes"]))
 check("Routes input bytes, mode and mtime remain exact",pin(routes)==routepin)
except BaseException as exc:error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
after=fence()
check("Source, oracle and expectations bytes, modes and mtimes preserved",before==after)
check("All owned CLI children exited naturally and process groups are absent",len(commands)==2 and all(x["status"]>=0 and not x["forced"] and x["group_absent"] for x in commands))
receipt=dict(schema="hamon.queued-routes.withdrawal-integration.v1",phase="post-intake current-source integration",utc=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),python=sys.version,source=str(SOURCE),passed=sum(x["accepted"]for x in checks),failed=sum(not x["accepted"]for x in checks),error=error,checks=checks,commands=commands,state=state,before=before,after=after,boundary=expected["boundary"])
with (OUT/"RECEIVING.json").open("x") as f:json.dump(receipt,f,ensure_ascii=False,indent=2);f.write("\n")
print(json.dumps({k:receipt[k]for k in ["phase","passed","failed","error"]}))
sys.exit(2 if error else 1 if receipt["failed"] else 0)
