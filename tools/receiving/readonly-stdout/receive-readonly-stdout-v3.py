"""Original-first actual read-only CLI stdout receiving; owned synthetic inputs."""
from __future__ import annotations
import hashlib,json,os,pathlib,shutil,signal,subprocess,sys,time,traceback
sys.dont_write_bytecode=True
SOURCE=pathlib.Path(sys.argv[1]).resolve();OUT=pathlib.Path(sys.argv[2]).resolve();PHASE=sys.argv[3]
BASE=pathlib.Path(sys.argv[4]).resolve() if len(sys.argv)>4 else None
SELF=pathlib.Path(__file__).resolve();EXPECT=SELF.with_name("stdout-expectations-v2.json")
E=json.loads(EXPECT.read_bytes())
if PHASE not in {"original","candidate"}:raise ValueError("phase must be original or candidate")
if PHASE=="candidate" and BASE is None:raise ValueError("candidate needs preserved original controls")
OUT.mkdir()
checks=[];commands=[];input_checks=[];healthy={};error=None
def pin(p):
 b=p.read_bytes();s=p.stat();return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),mode=s.st_mode&511,mtime_ns=s.st_mtime_ns)
def source_fence():
 return {str(p):pin(p)for p in [*sorted((SOURCE/"fanout_engine").glob("*.py")),SELF,EXPECT]}
def check(name,ok,**details):checks.append(dict(name=name,accepted=bool(ok),**details))
def absent(pid):
 try:os.killpg(pid,0)
 except ProcessLookupError:return True
 return False
def inputs():
 paths=[OUT/"plan.json",OUT/"routes.json",*sorted(OUT.glob("retained.sqlite3*"))]
 return {p.name:pin(p)for p in paths if p.is_file()}
def run(name,args,label,mode="pipe"):
 before=inputs();sink=None
 # A genuine closed descriptor reaches Python startup; sys.stdout is never patched.
 if mode=="full":sink=open("/dev/full","wb")
 command=[sys.executable,"-B","-m","fanout_engine."+name,*args]
 p=subprocess.Popen(command,cwd=SOURCE,env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONPATH=""),stdin=subprocess.DEVNULL,stdout=sink if sink else subprocess.PIPE,stderr=subprocess.PIPE,preexec_fn=(lambda:os.close(1)) if mode=="closed" else None,start_new_session=True)
 forced=False
 try:
  try:out,err=p.communicate(timeout=8)
  except subprocess.TimeoutExpired:
   forced=True;os.killpg(p.pid,signal.SIGTERM)
   try:out,err=p.communicate(timeout=1)
   except subprocess.TimeoutExpired:
    os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate(timeout=1)
 finally:
  if sink:sink.close()
 item=dict(cli=name,label=label,mode=mode,command=command,pid=p.pid,status=p.returncode,forced=forced,group_absent=absent(p.pid),stdout=(out or b"").decode("utf-8","replace"),stderr=err.decode("utf-8","replace"))
 commands.append(item);after=inputs();input_checks.append(dict(label=label,before=before,after=after,unchanged=before==after))
 return item
def clean(item,prefix,code,missing=False):
 err=item["stderr"].strip()
 return item["status"]==code and not item["stdout"] and err.startswith(prefix) and len(err.splitlines())==1 and "Traceback" not in err and "AttributeError" not in err and len(err)>len(prefix) and (not missing or "output" in err.lower() or "stdout" in err.lower())
before=source_fence()
try:
 if PHASE=="original":
  sys.path.insert(0,str(SOURCE))
  from fanout_engine import Ledger,Plan
  plan=Plan.from_dict(E["plan"])
  with Ledger(OUT/"retained.sqlite3")as ledger:
   ledger.record_plan(plan)
   ledger.mark_dispatching(plan.project_id,"root","fictional-worker",{"model":"m","effort":"low"})
   ledger.mark_running(plan.project_id,"root","fictional-task")
   ledger.mark_completed(plan.project_id,"root","fixture://complete",E["evidence"])
  (OUT/"plan.json").write_text(json.dumps(E["plan"],ensure_ascii=False),encoding="utf-8")
  (OUT/"routes.json").write_text(json.dumps(E["routing"]),encoding="utf-8")
 else:
  for name in ["retained.sqlite3","plan.json","routes.json"]:shutil.copyfile(BASE/name,OUT/name)
  original=json.loads((BASE/"RECEIVING.json").read_bytes())
  if original["phase"]!="original" or original["error"] is not None:raise ValueError("original control receipt unavailable")
 project=E["plan"]["project"]
 common={"preview":["--plan",str(OUT/"plan.json"),"--routes",str(OUT/"routes.json")],"inspect":["--database",str(OUT/"retained.sqlite3"),"--project",project],"history":["--database",str(OUT/"retained.sqlite3"),"--project",project],"projects":["--database",str(OUT/"retained.sqlite3")]}
 for name,spec in E["commands"].items():
  args=common[name]
  first=run(name,args,name+" healthy before");report=json.loads(first["stdout"])
  if name=="preview":identity=report["plan"]["project"]==project and report["dependency_ready_without_completions"]==["root"]
  elif name=="inspect":identity=report["project_id"]==project and report["queued_ready_ids"]==["child"]
  elif name=="history":identity=report["project_id"]==project and [x["event"]for x in report["events"]]==["plan_recorded","dispatch_started","dispatch_accepted","completed"]
  else:identity=report["project_count"]==1 and report["projects"][0]["project_id"]==project and report["projects"][0]["part_count"]==2
  match=PHASE=="original" or first["stdout"]==original["healthy"][name]
  healthy[name]=first["stdout"]
  check(name+" healthy JSON identity and original compatibility",first["status"]==0 and not first["stderr"] and identity and match)
  closed=run(name,args,name+" absent stdout","closed")
  check(name+" absent stdout follows existing handled exit and useful single diagnostic",clean(closed,spec["prefix"],spec["outputExit"],True),observedStatus=closed["status"],expectedStatus=spec["outputExit"],stderr=closed["stderr"])
  full=run(name,args,name+" existing failing stdout stream","full")
  check(name+" existing stream failure retains handled diagnostic",clean(full,spec["prefix"],spec["outputExit"]),stderr=full["stderr"])
  later=run(name,args,name+" healthy after")
  check(name+" later healthy output unchanged",later["status"]==0 and not later["stderr"] and later["stdout"]==first["stdout"])
  if spec["fileOutput"]:
   target=OUT/(name+"-report.json")
   saved=run(name,[*args,"--output",str(target)],name+" file output with stdout closed","closed")
   check(name+" file output bypasses absent stdout unchanged",saved["status"]==0 and not saved["stdout"] and not saved["stderr"] and target.read_bytes()==first["stdout"].encode())
  if name=="preview":badargs=["--plan",str(OUT/"absent-plan.json"),"--routes",str(OUT/"routes.json")]
  elif name=="projects":badargs=["--database",str(OUT/"absent.sqlite3")]
  else:badargs=["--database",str(OUT/"retained.sqlite3"),"--project","missing-project"]
  invalid=run(name,badargs,name+" input refusal with stdout closed","closed")
  check(name+" input refusal still precedes output access",clean(invalid,spec["prefix"],spec["invalidExit"]) and not (OUT/"absent.sqlite3").exists())
except BaseException as exc:error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
after=source_fence()
check("All declared inputs and SQLite sidecars unchanged around every actual CLI",len(input_checks)==23 and all(x["unchanged"]for x in input_checks))
check("Source and frozen oracle/expectation bytes modes and mtimes unchanged",before==after)
check("All 23 owned children exited naturally and process groups are absent",len(commands)==23 and all(not x["forced"] and x["group_absent"] and x["status"]>=0 for x in commands))
receipt=dict(schema="hamon.readonly-cli.stdout-receiving.v1",phase=PHASE,source=str(SOURCE),originalControls=str(BASE)if BASE else None,utc=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),python=sys.version,passed=sum(x["accepted"]for x in checks),failed=sum(not x["accepted"]for x in checks),error=error,checks=checks,commands=commands,healthy=healthy,inputChecks=input_checks,before=before,after=after,boundary=E["boundary"])
with (OUT/"RECEIVING.json").open("x")as f:json.dump(receipt,f,ensure_ascii=False,indent=2);f.write("\n")
print(json.dumps({k:receipt[k]for k in ["phase","passed","failed","error"]}))
sys.exit(2 if error else 1 if receipt["failed"]else 0)
