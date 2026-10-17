#!/usr/bin/env python3
from pathlib import Path
import argparse, hashlib, json, sqlite3, sys
p=argparse.ArgumentParser()
p.add_argument("--source",required=True)
p.add_argument("--database",required=True)
p.add_argument("--result",required=True)
args=p.parse_args()
sys.path.insert(0,args.source)
from fanout_engine import Ledger, LedgerError, Plan, EffortRouter, Route, dispatch_ready, inspect_project
results=[]
def check(name,ok,**detail): results.append({"name":name,"pass":bool(ok),**detail})
def snap(ledger):
    return hashlib.sha256("\n".join(ledger._db.iterdump()).encode()).hexdigest()
def setup(ledger,name):
    plan=Plan.from_dict({"project":name,"parts":[{"id":"first","instruction":"Independent local receiving"}]})
    ledger.record_plan(plan)
    ledger.mark_dispatching(name,"first","fixture-worker",{"model":"fixture-model","effort":"low"})
    return plan
def row(ledger,name):
    return dict(ledger._db.execute("SELECT * FROM parts WHERE project_id=? AND part_id='first'",(name,)).fetchone())
class AdaptedTask(str):
    adaptations=0
    def __conform__(self,protocol):
        type(self).adaptations+=1
        return "wrong-SQLite-adapted-id"
    def __str__(self): return "wrong-display-id"
class EqualTask(str):
    def __eq__(self,other): return True
    __hash__=str.__hash__
class FalseTask(str):
    def __bool__(self): return False
literal="  task/Ω#1  "
with Ledger(args.database) as ledger:
    invalid=[("none",None),("integer",73),("boolean",True),("float",0.25),
             ("bytes",b"task"),("bytearray",bytearray(b"task")),("empty",""),
             ("whitespace","\t \r\n"),("surrogate","\ud800")]
    for name,value in invalid:
        project="invalid-"+name
        setup(ledger,project)
        before=snap(ledger)
        error=None
        try:ledger.mark_running(project,"first",value)
        except Exception as exc:error=type(exc).__name__
        after=snap(ledger)
        check("invalid-"+name,error=="LedgerError" and before==after,
              error=error,rows_events_unchanged=before==after,state=row(ledger,project)["state"])
    setup(ledger,"adaptation")
    error=None
    try:ledger.mark_running("adaptation","first",AdaptedTask(literal))
    except Exception as exc:error=type(exc).__name__
    record=row(ledger,"adaptation")
    accepted=[e for e in ledger.events("adaptation","first") if e["event"]=="dispatch_accepted"]
    inspected=inspect_project(ledger,"adaptation")["parts"][0]
    check("literal-receipt-parity",error is None and record["task_id"]==literal and
          len(accepted)==1 and accepted[0]["detail"]["task_id"]==literal and inspected["task_id"]==literal,
          error=error,row_task=record["task_id"],event_task=accepted[0]["detail"]["task_id"] if accepted else None,
          inspection_task=inspected["task_id"],adaptation_calls=AdaptedTask.adaptations)
    before=snap(ledger);error=None
    try:ledger.mark_running("adaptation","first",literal)
    except Exception as exc:error=type(exc).__name__
    check("same-literal-is-idempotent",error is None and before==snap(ledger),error=error)
    setup(ledger,"equality")
    ledger.mark_running("equality","first","known-task")
    before=snap(ledger);error=None
    try:ledger.mark_running("equality","first",EqualTask("different-task"))
    except Exception as exc:error=type(exc).__name__
    check("different-equality-override-refused",error=="LedgerError" and before==snap(ledger),
          error=error,rows_events_unchanged=before==snap(ledger))
    setup(ledger,"false-truth")
    error=None
    try:ledger.mark_running("false-truth","first",FalseTask("literal-false-truth-task"))
    except Exception as exc:error=type(exc).__name__
    check("literal-text-ignores-subclass-truthiness",error is None and
          row(ledger,"false-truth")["task_id"]=="literal-false-truth-task",error=error)
    plan=Plan.from_dict({"project":"dispatch-course","parts":[
        {"id":"first","instruction":"Local fixture dispatch"},{"id":"dependent","instruction":"Must stay queued","depends_on":["first"]}]})
    router=EffortRouter({"fixture-model":["low"]},pool=[Route("fixture-model","low")])
    class Hub:
        def __init__(self):self.calls=[]
        def submit(self,part,**kwargs):
            self.calls.append((part.id,kwargs["idempotency_key"]))
            return {"task_id":AdaptedTask("dispatch-literal-task")}
    hub=Hub()
    first=dispatch_ready(plan,ledger,hub,router,worker_for=lambda part:"fixture-worker")
    before=snap(ledger)
    second=dispatch_ready(plan,ledger,hub,router,worker_for=lambda part:"fixture-worker")
    observed=inspect_project(ledger,"dispatch-course")
    check("dispatch-once-retains-literal",len(hub.calls)==1 and
          row(ledger,"dispatch-course")["task_id"]=="dispatch-literal-task" and
          before==snap(ledger) and observed["blocked_queued_ids"]==["dependent"],
          submit_calls=len(hub.calls),task_id=row(ledger,"dispatch-course")["task_id"],
          second_dispatch_rows_events_unchanged=before==snap(ledger),
          dependent_state=observed["parts"][1]["state"])
with Ledger(args.database) as reopened:
    observed=inspect_project(reopened,"adaptation")["parts"][0]
    accepted=[e for e in reopened.events("adaptation","first") if e["event"]=="dispatch_accepted"]
    check("reopened-row-event-inspection-parity",row(reopened,"adaptation")["task_id"]==literal and
          observed["task_id"]==literal and len(accepted)==1 and accepted[0]["detail"]["task_id"]==literal,
          task_id=observed["task_id"])
    integrity=reopened._db.execute("PRAGMA integrity_check").fetchone()[0]
    check("sqlite-integrity",integrity=="ok",result=integrity)
report={"source":args.source,"database":args.database,"checks":results,"passed":sum(x["pass"] for x in results),
        "total":len(results),"failed_names":[x["name"] for x in results if not x["pass"]],
        "database_sha256":hashlib.sha256(Path(args.database).read_bytes()).hexdigest()}
Path(args.result).write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
print(json.dumps({"passed":report["passed"],"total":report["total"],"failed_names":report["failed_names"]}))
