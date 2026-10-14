"""Original-only queued-route consumer controls; synthetic local state, no Hub."""
from __future__ import annotations
import hashlib, json, os, pathlib, signal, subprocess, sys, time
sys.dont_write_bytecode = True
SOURCE = pathlib.Path(sys.argv[1]).resolve()
OUT = pathlib.Path(sys.argv[2]).resolve()
SELF = pathlib.Path(__file__).resolve()
EXPECT = SELF.with_name("original-expectations-v1.json")
OUT.mkdir()
expected = json.loads(EXPECT.read_bytes())
checks, commands = [], []
def check(name, accepted, **details):
    checks.append(dict(name=name, accepted=bool(accepted), **details))
def pin(p):
    b=p.read_bytes(); s=p.stat()
    return dict(bytes=len(b), sha256=hashlib.sha256(b).hexdigest(), mode=s.st_mode&511, mtime_ns=s.st_mtime_ns)
def group_absent(pid):
    try: os.killpg(pid,0)
    except ProcessLookupError: return True
    return False
def run(arguments):
    env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH="")
    p=subprocess.Popen([sys.executable,"-B",*arguments], cwd=SOURCE, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    forced=False
    try: out,err=p.communicate(timeout=8)
    except subprocess.TimeoutExpired:
        forced=True
        os.killpg(p.pid,signal.SIGTERM)
        try: out,err=p.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL)
            out,err=p.communicate(timeout=1)
    item=dict(arguments=arguments,pid=p.pid,status=p.returncode,forced=forced,group_absent=group_absent(p.pid),stdout=out.decode("utf-8","replace"),stderr=err.decode("utf-8","replace"))
    commands.append(item)
    return item
pins={str(p):pin(p) for p in SOURCE.rglob("*") if p.is_file()}
pins[str(SELF)]=pin(SELF); pins[str(EXPECT)]=pin(EXPECT)
error=None
try:
    sys.path.insert(0,str(SOURCE))
    from fanout_engine import Ledger, Plan
    deps={"zulu":["done"],"blocked_unknown":["unknown"],"blocked_running":["running"],"blocked_failed":["failed"],"blocked_dispatching":["dispatching"],"blocked_queued":["alpha"]}
    document={"project":expected["project"],"parts":[{"id":p,"instruction":"Authored local step "+p+" — 雪","depends_on":deps.get(p,[])} for p in expected["partOrder"]]}
    plan=Plan.from_dict(document)
    database=OUT/"retained.sqlite3"
    evidence={"source":"independent receiver","locator":"fixture://local","finding":"authored state, no external work"}
    route={"model":"model-a","effort":"low"}
    with Ledger(database) as ledger:
        ledger.record_plan(plan)
        for name in ["unknown","done","running","failed","dispatching"]:
            ledger.mark_dispatching(plan.project_id,name,"fictional-worker",route)
            if name=="unknown": ledger.mark_outcome_unknown(plan.project_id,name,evidence)
            elif name!="dispatching":
                ledger.mark_running(plan.project_id,name,"fictional-task-"+name)
                if name=="done": ledger.mark_completed(plan.project_id,name,"fixture://complete",evidence)
                elif name=="failed": ledger.mark_failed(plan.project_id,name,evidence)
    planfile=OUT/"plan.json"; planfile.write_text(json.dumps(document,ensure_ascii=False),encoding="utf-8")
    routes={"catalog":{"model-a":["low","high"],"model-b":["low","max"]},"pool":[{"model":"model-a","effort":"low"},{"model":"model-b","effort":"low"}],"explicit_routes":{"zulu":{"model":"model-b","effort":"max"},"blocked_unknown":{"model":"model-a","effort":"high"}},"step_up":{"model":"model-a","effort":"high"}}
    routefile=OUT/"routes.json"; routefile.write_text(json.dumps(routes),encoding="utf-8")
    for p in [database,planfile,routefile]: pins[str(p)]=pin(p)
    native=run(["-m","fanout_engine.inspect","--database",str(database),"--project",plan.project_id])
    report=json.loads(native["stdout"])
    check("Original inspector CLI succeeds",native["status"]==0 and not native["stderr"])
    check("Authored order and mixed-state counts retained",[x["id"] for x in report["parts"]]==expected["partOrder"] and report["state_counts"]==expected["stateCounts"])
    check("Retained queued-ready and blocked IDs match literal expectation",report["queued_ready_ids"]==expected["retainedQueuedReady"] and report["blocked_queued_ids"]==expected["retainedBlockedQueued"])
    preview=run(["-m","fanout_engine.preview","--plan",str(planfile),"--routes",str(routefile)])
    initial=json.loads(preview["stdout"])
    check("Original authored preview CLI succeeds",preview["status"]==0 and not preview["stderr"])
    check("Initial preview is distinct from current readiness",initial["dependency_ready_without_completions"]==expected["initialDependencyReady"] and initial["dependency_ready_without_completions"]!=report["queued_ready_ids"])
    chosen={x["part_id"]:x for x in initial["routes"]}
    check("Exact configured explicit and pool routes exist",all(chosen[k]["route"]==v for k,v in expected["chosenRoutes"].items()) and chosen["zulu"]["route_source"]=="explicit" and chosen["alpha"]["route_source"]=="pool")
    absent=run(["-m","fanout_engine.queued_routes","--database",str(database),"--project",plan.project_id,"--routes",str(routefile)])
    check("New CLI absence is expected capability gap",not (SOURCE/"fanout_engine/queued_routes.py").exists() and absent["status"]!=0 and "No module named fanout_engine.queued_routes" in absent["stderr"] and not absent["stdout"])
except Exception as exc:
    import traceback
    error=dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc())
after={}
for name,before in pins.items():
    try: after[name]=pin(pathlib.Path(name))
    except Exception as exc: after[name]={"error":str(exc)}
check("All input source and fixture bytes/modes/mtimes preserved",pins==after)
check("All owned children exited naturally and groups are absent",all(x["status"]>=0 and not x["forced"] and x["group_absent"] for x in commands))
receipt=dict(schema="hamon.queued-routes.original-controls.v1",phase="original-only",source=str(SOURCE),observedUtc=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),python=sys.version,passed=sum(x["accepted"] for x in checks),failed=sum(not x["accepted"] for x in checks),error=error,checks=checks,commands=commands,before=pins,after=after,boundary="Original actual local CLI and authored SQLite states. No candidate, provider, Hub submission, native probe or installed-state claim. CLI absence is expected new capability absence.")
with (OUT/"RECEIVING.json").open("x",encoding="utf-8") as f:json.dump(receipt,f,ensure_ascii=False,indent=2);f.write("\n")
print(json.dumps({k:receipt[k] for k in ["phase","passed","failed","error"]}))
sys.exit(2 if error else 1 if receipt["failed"] else 0)
