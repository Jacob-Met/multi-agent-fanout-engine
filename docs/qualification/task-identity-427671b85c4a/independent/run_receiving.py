#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,os,platform,shutil,subprocess,sys,time,traceback
ROOT=Path(__file__).resolve().parent
SOURCE=Path("/home/jacob/hamon-fanout-427671b85c4a/repo-current")
BASE=ROOT/"parent-source"
BASE.mkdir(exist_ok=False)
receipt={"schema":"hamon.fanout-independent-native-receiving/1","status":"running",
 "repository":"Jacob-Met/multi-agent-fanout-engine","candidate_commit":"a5959edc361b4345ec6c356e8e40a294b1e6b3d6",
 "candidate_tree":"6b6ac5d71602fece8de8659b401a2cf00a7d24a9","parent_commit":"484ad9270b6c5e49db87171eb26ac516d592ddd6",
 "host":platform.node(),"python":platform.python_version(),"filesystem":"unique tmpfs after home ENOSPC",
 "commands":[],"started_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
def require(ok,msg):
 if not ok:raise RuntimeError(msg)
def sha(data):return hashlib.sha256(data).hexdigest()
def gitblob(data):return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()
def snapshot():
 return {str(p.relative_to(SOURCE)):{"sha256":sha(p.read_bytes()),"git_blob":gitblob(p.read_bytes())}
         for p in sorted((SOURCE/"fanout_engine").glob("*.py"))}
try:
 before=snapshot();receipt["source_before"]=before
 require(before["fanout_engine/ledger.py"]["sha256"]=="c07a96ea8cf7aaaea85623120b6eb3adaafa227744d68be40111f933dd8a9dd8","candidate source changed")
 original=(ROOT/"parent-ledger.py").read_bytes()
 require(gitblob(original)=="c7cbd46e260b964b1a8a62eb425ae4e2861ddd4f","parent source mismatch")
 for p in (SOURCE/"fanout_engine").glob("*.py"):
  q=BASE/"fanout_engine"/p.name;q.parent.mkdir(exist_ok=True)
  q.write_bytes(original if p.name=="ledger.py" else p.read_bytes())
 receipt["parent_ledger_sha256"]=sha(original)
 receipt["course_sha256"]=sha((ROOT/"independent_course.py").read_bytes())
 for name,source in [("parent",BASE),("candidate",SOURCE)]:
  command=[sys.executable,"-B",str(ROOT/"independent_course.py"),"--source",str(source),
    "--database",str(ROOT/(name+".sqlite3")),"--result",str(ROOT/(name+"-result.json"))]
  result=subprocess.run(command,env=dict(os.environ,PYTHONDONTWRITEBYTECODE="1",TMPDIR=str(ROOT)),
                        capture_output=True,timeout=30)
  (ROOT/(name+".stdout")).write_bytes(result.stdout);(ROOT/(name+".stderr")).write_bytes(result.stderr)
  receipt["commands"].append({"name":name,"argv":command,"exit_code":result.returncode,
    "stdout_sha256":sha(result.stdout),"stderr_sha256":sha(result.stderr)})
  print(json.dumps({"name":name,"exit_code":result.returncode,"stdout":result.stdout.decode(),"stderr":result.stderr.decode()}),flush=True)
  require(result.returncode==0,name+" execution failed")
  report=json.loads((ROOT/(name+"-result.json")).read_bytes())
  receipt[name]=report
  receipt[name+"_result_sha256"]=sha((ROOT/(name+"-result.json")).read_bytes())
 require(receipt["candidate"]["passed"]==receipt["candidate"]["total"]==16,"candidate independent course failed")
 require(len(receipt["parent"]["failed_names"])>=5,"parent did not reproduce enough meaningful counterexamples")
 receipt["source_after"]=snapshot()
 require(receipt["source_after"]==before,"candidate module bytes changed")
 receipt["source_snapshot_unchanged"]=True
 receipt["status"]="pass"
except BaseException as error:
 receipt["status"]="failed";receipt["error"]=type(error).__name__+": "+str(error);receipt["traceback"]=traceback.format_exc()
finally:
 receipt["finished_utc"]=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())
 data=(json.dumps(receipt,sort_keys=True,indent=2)+"\n").encode()
 (ROOT/"native-receiving.json").write_bytes(data)
 print(json.dumps({"status":receipt["status"],"path":str(ROOT/"native-receiving.json"),"sha256":sha(data),"bytes":len(data),"error":receipt.get("error")}),flush=True)
sys.exit(0 if receipt["status"]=="pass" else 1)
