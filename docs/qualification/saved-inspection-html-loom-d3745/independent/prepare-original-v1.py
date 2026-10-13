from pathlib import Path
import hashlib,json,os,shutil,stat,subprocess,sys,datetime
root=Path("/workspace/scratch/d3745ea0f44f/root-fanout-html")
source=Path("/dev/shm/loom-d3745-fanout-comparison-html/original")
metadata=json.loads(source.parent.joinpath("original-source.json").read_bytes())
destination=root/"original"
destination.mkdir()
records=[]
for row in metadata["files"]:
 if not row["path"].startswith("fanout_engine/"):continue
 b=(source/row["path"]).read_bytes()
 assert len(b)==row["bytes"] and hashlib.sha256(b).hexdigest()==row["sha256"]
 assert hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()==row["git_blob"]
 target=destination/row["path"];target.parent.mkdir(exist_ok=True)
 with target.open("xb") as f:f.write(b)
 target.chmod(0o644);records.append(row)
fixtures=root/"fixtures";fixtures.mkdir()
first={"project_id":"handoff <&> Ω","plan_digest":"opaque-declared-digest","ready":True,"nullable":None,"parts":[{"id":"inventory<&>","state":"complete","count":1,"accepted":False},{"id":'audit "Ω"',"state":"outcome_unknown","task_ref":None},{"id":"handoff","state":"blocked","offset":-0.0}]}
second={"project_id":"handoff <&> Ω","plan_digest":"opaque-declared-digest","ready":1,"parts":[{"id":"handoff","state":"ready","offset":0.0},{"id":"inventory<&>","state":"complete","count":1.0,"accepted":0},{"id":'audit "Ω"',"state":"complete","task_ref":None}]}
order=json.loads(json.dumps(first));order["parts"]=list(reversed(order["parts"]))
bad=json.loads(json.dumps(second));bad["plan_digest"]="different-declaration"
for name,value in [("first",first),("second",second),("order-only",order),("mismatched",bad)]:
 with (fixtures/(name+".json")).open("xb") as f:f.write((json.dumps(value,ensure_ascii=False,indent=2)+"\n").encode())
receipt={"schema":"hamon.root.fanout-html-original-oracles.v1","candidate_exposed":False,"time":datetime.datetime.now(datetime.timezone.utc).isoformat(),"python":sys.version,"source":records,"commands":[]}
for label,other in [("typed","second"),("order","order-only")]:
 command=[sys.executable,"-B","-m","fanout_engine.compare_inspections","--first",str(fixtures/"first.json"),"--second",str(fixtures/(other+".json"))]
 result=subprocess.run(command,cwd=destination,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 assert result.returncode==0 and not result.stderr
 report=json.loads(result.stdout)
 assert report["part_order_changed"] is True and report["same_input_bytes"] is False and report["same_saved_values"] is False
 if label=="typed":
  assert report["changed_part_ids"]==["inventory<&>",'audit "Ω"',"handoff"]
  expected_fields=[["accepted","count"],["state"],["offset","state"]]
  assert [[f["field"] for f in r["fields"]] for r in report["part_changes"]]==expected_fields
  assert [f["field"] for f in report["top_level_changes"]]==["nullable","ready"]
  assert report["top_level_changes"][0]["second"]=={"present":False}
  encoded=json.dumps(report,sort_keys=True,separators=(",",":"))
  for typed in ['"value":false','"value":0','"value":1.0','"value":-0.0','"value":0.0']:assert typed in encoded
 else:
  assert report["changed_part_ids"]==[] and report["top_level_changes"]==[] and report["part_changes"]==[]
 for side,value in [("first",first),("second",second if label=="typed" else order)]:
  assert json.dumps(report[side]["document"],sort_keys=True)==json.dumps(value,sort_keys=True)
 for extension,body in [("json",result.stdout),("stderr",result.stderr)]:
  with (fixtures/(label+"-oracle."+extension)).open("xb") as f:f.write(body)
 receipt["commands"].append({"label":label,"argv":command,"exit":result.returncode,"stdout_sha256":hashlib.sha256(result.stdout).hexdigest(),"stdout_bytes":len(result.stdout),"stderr_bytes":len(result.stderr)})
for row in records:
 assert hashlib.sha256((destination/row["path"]).read_bytes()).hexdigest()==row["sha256"]
receipt["original_bytes_preserved"]=True
receipt["fixture_pins"]=[{"path":str(p.relative_to(root)),"bytes":len(p.read_bytes()),"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(fixtures.iterdir())]
with (root/"original-oracles.json").open("xb") as f:f.write((json.dumps(receipt,indent=2)+"\n").encode())
print(json.dumps(receipt))
