"""Independent advisory-route CLI receiving, frozen before candidate intake."""
from __future__ import annotations
import hashlib,json,os,pathlib,signal,sqlite3,subprocess,sys,time,traceback
sys.dont_write_bytecode=True
SOURCE=pathlib.Path(sys.argv[1]).resolve()
BASE=pathlib.Path(sys.argv[2]).resolve()
OUT=pathlib.Path(sys.argv[3]).resolve()
SELF=pathlib.Path(__file__).resolve()
EXPECT=SELF.with_name("candidate-expectations-v1.json")
AUDIT=SELF.with_name("observe-queued-cli-v1.py")
E=json.loads(EXPECT.read_bytes())
OUT.mkdir()
checks=[];commands=[];error=None
def check(name,value,**extra):checks.append(dict(name=name,accepted=bool(value),**extra))
def pin(p):
 b=p.read_bytes();s=p.stat()
 return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),mode=s.st_mode&511,mtime_ns=s.st_mtime_ns)
def absent(pid):
 try:os.killpg(pid,0)
 except ProcessLookupError:return True
 return False
source_paths=[p for p in SOURCE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
pins={str(p):pin(p) for p in source_paths+[SELF,EXPECT,AUDIT]}
for name in ["retained.sqlite3","routes.json","plan.json"]:
 pins[str(BASE/name)]=pin(BASE/name)
def write(name,value,raw=False):
 p=OUT/name
 b=value if raw else json.dumps(value,ensure_ascii=False).encode()
 with p.open("xb") as f:f.write(b)
 pins[str(p)]=pin(p)
 return p
def invoke(label,arguments,closed_stdout=False):
 log=OUT/("audit-"+str(len(commands)+1)+".jsonl")
 with log.open("xb"):pass
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",PYTHONPATH="")
 kw=dict(cwd=OUT,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
 if closed_stdout:kw["preexec_fn"]=lambda:os.close(1)
 p=subprocess.Popen([sys.executable,"-B",str(AUDIT),str(SOURCE),str(OUT),str(log),*arguments],**kw)
 forced=False
 try:out,err=p.communicate(timeout=8)
 except subprocess.TimeoutExpired:
  forced=True
  os.killpg(p.pid,signal.SIGTERM)
  try:out,err=p.communicate(timeout=1)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate(timeout=1)
 r=dict(label=label,arguments=arguments,status=p.returncode,stdout=out.decode("utf-8","replace"),stderr=err.decode("utf-8","replace"),forced=forced,group_absent=absent(p.pid),pid=p.pid,observations=[json.loads(line) for line in log.read_text().splitlines()])
 try:r["json"]=json.loads(r["stdout"])
 except ValueError:r["json"]=None
 commands.append(r)
 return r
def clean(r):return not r["forced"] and r["group_absent"] and r["status"]>=0
def refused(label,arguments,status=2,no_io=False):
 r=invoke(label,arguments)
 check(label,clean(r) and r["status"]==status and not r["stdout"] and bool(r["stderr"]) and (not no_io or not r["observations"]),command=len(commands)-1)
 return r
try:
 database=write("retained #% 雪.sqlite3",(BASE/"retained.sqlite3").read_bytes(),True)
 routes=write("routes.json",(BASE/"routes.json").read_bytes(),True)
 project=E["baseReport"]["project_id"]
 args=["--database",str(database),"--project",project,"--routes",str(routes)]
 original_route=json.loads(routes.read_bytes())
 r=invoke("Current mixed-state route projection",args)
 check("Complete current report matches frozen original-derived literal schema",clean(r) and r["status"]==0 and not r["stderr"] and r["json"]==E["baseReport"],command=len(commands)-1)
 connections=[x for x in r["observations"] if x["event"]=="sqlite3.connect"]
 check("Actual CLI opens one selected read-only SQLite connection",len(connections)==1 and connections[0]["database"]==database.as_uri()+"?mode=ro",command=len(commands)-1)
 r=invoke("Repeated advisory read",args)
 check("Repeat advisory report is identical without reservation",clean(r) and r["status"]==0 and not r["stderr"] and r["json"]==E["baseReport"],command=len(commands)-1)
 help_result=invoke("Help",["--help"])
 check("Help succeeds before fixture IO",clean(help_result) and help_result["status"]==0 and bool(help_result["stdout"]) and not help_result["stderr"] and not help_result["observations"],command=len(commands)-1)
 for label,bad in [
  ("Missing all required options",[]),
  ("Missing routes option",args[:4]),
  ("Duplicate database option",args+["--database",str(database)]),
  ("Duplicate project option",args+["--project",project]),
  ("Duplicate routes option",args+["--routes",str(routes)]),
  ("Abbreviated database option",["--dat",str(database),*args[2:]]),
  ("Unknown output-file option",args+["--output",str(OUT/"forbidden-output.json")]),
  ("Unexpected positional argument",args+["extra"])]:
  refused(label,bad,no_io=True)
 check("Invalid output option created no output path",not (OUT/"forbidden-output.json").exists())
 refused("Unknown project has distinct status3",["--database",str(database),"--project","not-recorded","--routes",str(routes)],3)
 missing=OUT/"no-existing-database.sqlite3"
 refused("Missing database does not initialize a ledger",["--database",str(missing),"--project",project,"--routes",str(routes)])
 check("Missing selected database remains absent",not missing.exists())
 refused("Missing routing file refuses",args[:-1]+[str(OUT/"missing-routes.json")])
 refused("Directory routing input refuses",args[:-1]+[str(OUT)])
 route_cases=[]
 def add(label,doc):
  p=write("route-"+str(len(route_cases)+1)+".json",doc);route_cases.append((label,p))
 def changed():
  return json.loads(json.dumps(original_route))
 d=changed();d["explicit_routes"]["not-in-plan"]={"model":"model-a","effort":"low"};add("Unknown override ID refuses",d)
 d=changed();d["explicit_routes"]["zulu"]={"model":"model-a","effort":"max"};add("Unauthorized ready override refuses",d)
 d=changed();d["explicit_routes"]["blocked_unknown"]={"model":"model-a","effort":"max"};add("Unauthorized blocked override refuses whole configuration",d)
 d=changed();d["explicit_routes"]["done"]={"model":"model-a","effort":"max"};add("Unauthorized completed override refuses whole configuration",d)
 d=changed();d["pool"][1]={"model":"outside-catalog","effort":"low"};add("Unauthorized pool refuses",d)
 d=changed();d["step_up"]={"model":"outside-catalog","effort":"high"};add("Unauthorized step-up refuses as metadata",d)
 d=changed();d["pool"]=[];add("Empty pool refuses",d)
 d=changed();d["pool"]=[{"model":"model-a","effort":"low"}]*257;add("Pool above256 refuses",d)
 d=changed();d["catalog"].update({("extra"+str(i)):["low"] for i in range(255)});add("Catalog above256 refuses",d)
 d=changed();d["extra"]=True;add("Unexpected routing field refuses",d)
 for label,p in route_cases:refused(label,args[:-1]+[str(p)])
 for label,b in [
  ("Malformed routing JSON refuses",b"{"),
  ("Repeated routing key refuses",b'{"catalog":{},"catalog":{},"pool":[]}'),
  ("Nonfinite routing JSON refuses",b'{"catalog":{},"pool":[],"extra":1e400}'),
  ("Invalid UTF8 routing refuses",b"\xff"),
  ("Routing above256KiB refuses",b" "*262145)]:
  p=write("raw-route-"+str(len(commands))+".json",b,True);refused(label,args[:-1]+[str(p)])
 empty_routes=changed();empty_routes.pop("step_up");empty_route=write("routes-no-step-up.json",empty_routes)
 wanted=json.loads(json.dumps(E["baseReport"]));wanted["configured_step_up"]=None;wanted["routing_input_sha256"]=hashlib.sha256(empty_route.read_bytes()).hexdigest()
 r=invoke("Absent configured step-up is null",args[:-1]+[str(empty_route)])
 check("Absent step-up returns exact null metadata",clean(r) and r["status"]==0 and not r["stderr"] and r["json"]==wanted,command=len(commands)-1)
 # Set up other authored ledgers using the frozen original package, never candidate APIs.
 sys.path.insert(0,E["originalSource"])
 from fanout_engine import Ledger,Plan
 idle=write("nothing-queued.sqlite3",database.read_bytes(),True)
 pins.pop(str(idle))
 ev={"source":"independent receiver","locator":"fixture://owned","finding":"authored terminal fixture"}
 with Ledger(idle) as ledger:
  for part in E["baseReport"]["parts"]:
   if part["state"]=="queued":
    ledger.mark_dispatching(project,part["id"],"fixture-worker",{"model":"model-a","effort":"low"})
    ledger.mark_running(project,part["id"],"fixture-task-"+part["id"])
    ledger.mark_failed(project,part["id"],ev)
 pins[str(idle)]=pin(idle)
 wanted=json.loads(json.dumps(E["baseReport"]));wanted["queued_ready_ids"]=[];wanted["blocked_queued_ids"]=[];wanted["routes"]=[];wanted["state_counts"]["failed"]+=wanted["state_counts"]["queued"];wanted["state_counts"]["queued"]=0
 states={x["id"]:("failed" if x["state"]=="queued" else x["state"]) for x in wanted["parts"]}
 for x in wanted["parts"]:
  x["state"]=states[x["id"]]
  for dep in x["unmet_dependencies"]:dep["state"]=states[dep["id"]]
 r=invoke("No queued work",["--database",str(idle),*args[2:]])
 check("Empty advisory route list succeeds with explicit state context",clean(r) and r["status"]==0 and not r["stderr"] and r["json"]==wanted,command=len(commands)-1)
 corrupt=write("late-corrupt.sqlite3",database.read_bytes(),True);pins.pop(str(corrupt))
 with sqlite3.connect(corrupt) as db:db.execute("UPDATE parts SET payload_json=? WHERE project_id=? AND part_id=?",("{",project,"blocked_queued"))
 db.close();pins[str(corrupt)]=pin(corrupt)
 refused("Malformed final retained part refuses complete report",["--database",str(corrupt),*args[2:]])
 oversize=OUT/"over256.sqlite3"
 big=Plan.from_dict({"project":project,"parts":[{"id":"part"+str(i),"instruction":"authored"} for i in range(257)]})
 with Ledger(oversize) as ledger:ledger.record_plan(big)
 pins[str(oversize)]=pin(oversize)
 plain_routes=write("plain-routes.json",{"catalog":{"model-a":["low"]},"pool":[{"model":"model-a","effort":"low"}]})
 refused("More than256 retained parts refuses",["--database",str(oversize),"--project",project,"--routes",str(plain_routes)])
 r=invoke("Actual interpreter starts with absent stdout",args,closed_stdout=True)
 check("Absent stdout is output failure status1 without traceback",clean(r) and r["status"]==1 and not r["stdout"] and "Traceback" not in r["stderr"],command=len(commands)-1)
except Exception as exc:error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
after={}
for name in pins:
 try:after[name]=pin(pathlib.Path(name))
 except Exception as exc:after[name]={"error":str(exc)}
check("All declared source/helper/baseline/input bytes and metadata unchanged",pins==after)
check("Every owned child exited naturally and group is absent",all(clean(x) for x in commands))
check("No observed network connection or child start inside CLI",all(not any(x["event"] in ("socket.connect","subprocess.Popen","os.system") for x in r["observations"]) for r in commands))
check("No observed write-open of owned input paths",all(not any(x["event"]=="open" and x["flags"]&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND) for x in r["observations"]) for r in commands))
receipt=dict(schema="hamon.queued-routes.independent-cli.v1",source=str(SOURCE),observedUtc=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),python=sys.version,passed=sum(x["accepted"] for x in checks),failed=sum(not x["accepted"] for x in checks),error=error,checks=checks,commands=commands,before=pins,after=after,boundary="Actual unchanged module entrypoint under a supported Python audit observer using runpy; cloud POSIX owned fixtures, no native/provider/installed claim. Audit hooks observe selected Python events, not OS-wide IO. Whole source/config and SQLite inputs are fenced. Full oracle frozen before candidate intake.")
receipt_path=OUT/"RECEIVING.json"
try:
 with receipt_path.open("x",encoding="utf-8") as f:json.dump(receipt,f,ensure_ascii=False,indent=2);f.write("\n")
except OSError as exc:
 print(json.dumps({"incomplete":True,"receiptWriteError":str(exc),"passed":receipt["passed"],"failed":receipt["failed"],"error":error}));sys.exit(3)
print(json.dumps({k:receipt[k] for k in ["passed","failed","error"]}))
sys.exit(2 if error else 1 if receipt["failed"] else 0)
