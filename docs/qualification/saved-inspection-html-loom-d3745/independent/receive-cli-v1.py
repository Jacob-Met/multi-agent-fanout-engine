"""Independent candidate-blind CLI receiving for saved-inspection HTML."""
from pathlib import Path
from html.parser import HTMLParser
import base64, hashlib, json, os, stat, subprocess, sys, traceback, urllib.parse, datetime
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
def canonical(v):return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False)
def snapshot(root):
 out={}
 for p in sorted(root.rglob("*")):
  st=p.lstat()
  if stat.S_ISLNK(st.st_mode):raise ValueError("unexpected symlink in watched input")
  if p.is_dir():out[str(p.relative_to(root))]={"kind":"directory","mode":stat.S_IMODE(st.st_mode)}
  elif p.is_file():
   b=p.read_bytes();out[str(p.relative_to(root))]={"kind":"file","bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),"mode":stat.S_IMODE(st.st_mode),"mtime_ns":st.st_mtime_ns}
  else:raise ValueError("unexpected input type")
 return out
class Page(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True);self.links=[];self.forbidden=[];self.text=[];self.stack=[];self.fragments=[]
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if tag in ("script","iframe","object","embed","form","input","textarea","button"):self.forbidden.append(tag)
  if any(k.lower().startswith("on") for k in attrs):self.forbidden.append("event attribute")
  if tag=="a":self.links.append(attrs)
  for attr in ("src","action"):
   if attrs.get(attr):self.forbidden.append(attr+"="+attrs[attr])
  if tag=="link" and attrs.get("href"):self.forbidden.append("external stylesheet")
  if tag in ("pre","code"):self.stack.append([tag,[]])
 def handle_endtag(self,tag):
  if self.stack and self.stack[-1][0]==tag:
   _,items=self.stack.pop();self.fragments.append("".join(items))
 def handle_data(self,data):
  self.text.append(data)
  for _,items in self.stack:items.append(data)
def inspect_html(content,oracle):
 page=Page();page.feed(content.decode("utf-8"));page.close()
 assert not page.forbidden,page.forbidden
 links=[a for a in page.links if a.get("href","").startswith("data:")]
 assert len(links)==1
 link=links[0];head,payload=link["href"].split(",",1)
 assert "application/json" in head and link.get("download")
 extracted=base64.b64decode(payload,validate=True) if ";base64" in head else urllib.parse.unquote_to_bytes(payload)
 assert extracted==oracle and extracted.endswith(b"\n")
 text="".join(page.text)
 assert "first" in text.lower() and "second" in text.lower()
 report=json.loads(oracle)
 assert report["first"]["input_sha256"] in text and report["second"]["input_sha256"] in text
 assert any(x in text.lower() for x in ("saved data","saved-data","saved inspection"))
 # Complete typed display values are additionally reviewed from the real page.
 # The embedded report equality is exact; no arbitrary HTML tag layout is required.
 return {"html_bytes":len(content),"html_sha256":hashlib.sha256(content).hexdigest(),"embedded_json_bytes":len(extracted),"embedded_json_sha256":hashlib.sha256(extracted).hexdigest(),"plain_text":text,"json_display_fragments":page.fragments,"link":link}
def main():
 if len(sys.argv)!=2:raise SystemExit("Usage: receive-cli-v1.py CANDIDATE")
 candidate=Path(sys.argv[1]).resolve()
 out=ROOT/"course-v1";out.mkdir()
 receipt={"schema":"hamon.root.fanout-inspection-html-cli-receiving.v1","started":datetime.datetime.now(datetime.timezone.utc).isoformat(),"argv":sys.argv,"python":sys.version,"checks":[],"commands":[],"accepted":False}
 watched={"fixtures":ROOT/"fixtures","original":ROOT/"original","candidate":candidate}
 receipt["before"]={k:snapshot(v) for k,v in watched.items()}
 def check(name,actual,expected):
  ok=canonical(actual)==canonical(expected);receipt["checks"].append({"name":name,"actual":actual,"expected":expected,"passed":ok})
  if not ok:raise AssertionError(name)
 def call(name,args,expected_exit):
  argv=[sys.executable,"-B","-m","fanout_engine.compare_inspections",*args]
  child=subprocess.Popen(argv,cwd=candidate,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  stdout,stderr=child.communicate(timeout=30)
  for suffix,b in [("stdout",stdout),("stderr",stderr)]:
   with (out/(name+"."+suffix)).open("xb") as f:f.write(b)
  receipt["commands"].append({"name":name,"argv":argv,"pid":child.pid,"exit":child.returncode,"stdout_bytes":len(stdout),"stderr_bytes":len(stderr),"stdout_sha256":hashlib.sha256(stdout).hexdigest(),"stderr_sha256":hashlib.sha256(stderr).hexdigest()})
  check(name+" exit",child.returncode,expected_exit)
  return stdout,stderr
 fixtures=ROOT/"fixtures"
 pair=["--first",str(fixtures/"first.json"),"--second",str(fixtures/"second.json")]
 oracle=(fixtures/"typed-oracle.json").read_bytes()
 try:
  baseline=json.loads((ROOT/"original-oracles.json").read_bytes())
  for row in baseline["source"]:
   if row["path"]!="fanout_engine/compare_inspections.py":
    check("unchanged dependency "+row["path"],hashlib.sha256((candidate/row["path"]).read_bytes()).hexdigest(),row["sha256"])
  for name,args in [("default-json",pair),("explicit-json",pair+["--format","json"])]:
   stdout,stderr=call(name,args,0);check(name+" bytes",base64.b64encode(stdout).decode(),base64.b64encode(oracle).decode());check(name+" stderr",len(stderr),0)
  html,stderr=call("typed-html",pair+["--format","html"],0);check("html stderr",len(stderr),0)
  parsed=inspect_html(html,oracle);receipt["typed_page"]=parsed
  destination=out/"typed.html"
  stdout,stderr=call("typed-file",pair+["--format","html","--output",str(destination)],0)
  check("new file equals stdout",base64.b64encode(destination.read_bytes()).decode(),base64.b64encode(html).decode());check("new file stdout",len(stdout),0);check("new file stderr",len(stderr),0)
  saved=destination.read_bytes()
  stdout,stderr=call("occupied-output",pair+["--format","html","--output",str(destination)],1)
  check("occupied file unchanged",destination.read_bytes()==saved,True);check("occupied stdout",len(stdout),0);check("occupied diagnostic",bool(stderr),True)
  stdout,stderr=call("input-output",pair+["--format","html","--output",str(fixtures/"first.json")],1)
  check("input refusal stdout",len(stdout),0);check("input refusal diagnostic",bool(stderr),True)
  missing=out/"mismatched.html"
  stdout,stderr=call("mismatched",["--first",str(fixtures/"first.json"),"--second",str(fixtures/"mismatched.json"),"--format","html","--output",str(missing)],2)
  check("invalid creates no file",missing.exists(),False);check("invalid stdout",len(stdout),0);check("invalid diagnostic",bool(stderr),True)
  stdout,stderr=call("order-only",["--first",str(fixtures/"first.json"),"--second",str(fixtures/"order-only.json"),"--format","html"],0)
  receipt["order_page"]=inspect_html(stdout,(fixtures/"order-oracle.json").read_bytes());check("order stderr",len(stderr),0)
  with (out/"order.html").open("xb") as f:f.write(stdout)
  receipt["accepted"]=True
 except BaseException:
  receipt["error"]=traceback.format_exc()
 finally:
  receipt["after"]={k:snapshot(v) for k,v in watched.items()}
  if receipt["before"]!=receipt["after"]:
   receipt["accepted"]=False;receipt["custody_error"]="watched inputs changed"
  receipt["finished"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
  with (out/"receipt.json").open("xb") as f:f.write((json.dumps(receipt,ensure_ascii=True,sort_keys=True,indent=2)+"\n").encode())
  print(json.dumps({"accepted":receipt["accepted"],"commands":len(receipt["commands"]),"checks":len(receipt["checks"]),"preserved":receipt["before"]==receipt["after"],"error":receipt.get("error")}))
 return 0 if receipt["accepted"] else 1
if __name__=="__main__":raise SystemExit(main())
