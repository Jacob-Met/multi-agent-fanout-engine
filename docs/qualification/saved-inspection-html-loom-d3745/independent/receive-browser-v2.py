"""Frozen independent file-origin browser opening; exact supplied inputs only."""
from pathlib import Path
import base64,hashlib,json,os,platform,pwd,shutil,stat,sys,traceback,datetime
from playwright.sync_api import sync_playwright
ROOT=Path(sys.argv[1]).resolve()
OUT=ROOT/"browser-v2"
OUT.mkdir()
receipt={"schema":"hamon.root.fanout-inspection-html-browser.v1","started":datetime.datetime.now(datetime.timezone.utc).isoformat(),"accepted":False,"checks":[],"requests":[],"page_errors":[],"browser_console_errors":[]}
def ident(p):
 b=p.read_bytes();return {"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest(),"mode":stat.S_IMODE(p.stat().st_mode)}
def check(name,actual,expected):
 ok=json.dumps(actual,sort_keys=True)==json.dumps(expected,sort_keys=True)
 receipt["checks"].append({"name":name,"actual":actual,"expected":expected,"passed":ok})
 if not ok:raise AssertionError(name)
manifest=json.loads((ROOT/"browser-inputs.json").read_bytes())
inputs={name:ROOT/"inputs"/name for name in ("typed.html","typed-oracle.json")}
receipt["before"]={name:ident(p) for name,p in inputs.items()}
context=None;profile=OUT/"owned-profile";closed_safely=True
try:
 check("host",platform.node(),"hamon-thinkpad")
 check("account",(pwd.getpwuid(os.getuid()).pw_name,os.getuid(),pwd.getpwuid(os.getuid()).pw_dir),("jacob",1000,"/home/jacob"))
 for name,p in inputs.items():
  for key in ("bytes","sha256"):check(name+" "+key,receipt["before"][name][key],manifest["inputs"][name][key])
 oracle=inputs["typed-oracle.json"].read_bytes();report=json.loads(oracle)
 check("fresh browser profile",profile.exists(),False)
 profile.mkdir()
 with sync_playwright() as pw:
  closed_safely=False
  context=pw.chromium.launch_persistent_context(str(profile),executable_path="/snap/chromium/current/usr/lib/chromium-browser/chrome",headless=True,accept_downloads=True,viewport={"width":1440,"height":1000},args=["--no-sandbox","--disable-background-networking"])
  receipt["browser_version"]=context.browser.version if context.browser else "persistent context"
  page=context.pages[0] if context.pages else context.new_page()
  page.on("request",lambda request:receipt["requests"].append(request.url))
  page.on("pageerror",lambda error:receipt["page_errors"].append(str(error)))
  page.on("console",lambda message:receipt["browser_console_errors"].append(message.text) if message.type=="error" else None)
  page.goto(inputs["typed.html"].as_uri(),wait_until="load")
  check("file origin",page.url,inputs["typed.html"].as_uri())
  check("no active/external embedding",page.locator("script,iframe,object,embed,form,input,textarea,button").count(),0)
  for details in page.locator("details").all():
   if not details.get_attribute("open"):details.locator("summary").click()
  text=page.locator("body").inner_text()
  check("first label visible","first" in text.lower(),True);check("second label visible","second" in text.lower(),True)
  check("saved data scope visible",any(s in text.lower() for s in ("saved data","saved-data","saved inspection")),True)
  for side in ("first","second"):check(side+" complete raw identity visible",report[side]["input_sha256"] in text,True)
  for token in ("nullable","ready","accepted","count","offset","outcome_unknown","blocked"):
   check("typed content visible "+token,token in text,True)
  receipt["desktop_body_text"]=text
  check("desktop no page overflow",page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"),True)
  page.screenshot(path=str(OUT/"desktop.png"),full_page=True)
  link=page.locator('a[download][href^="data:"]')
  check("one native download",link.count(),1)
  with page.expect_download() as received:link.click()
  download=received.value
  check("download failure",download.failure(),None)
  download.save_as(str(OUT/"comparison.json"))
  check("actual downloaded original JSON",base64.b64encode((OUT/"comparison.json").read_bytes()).decode(),base64.b64encode(oracle).decode())
  page.set_viewport_size({"width":390,"height":844})
  check("narrow no page overflow",page.evaluate("document.documentElement.scrollWidth <= innerWidth + 2"),True)
  check("download remains reachable",link.is_visible(),True)
  receipt["narrow_scroll_containers"]=page.evaluate("Array.from(document.querySelectorAll('*')).filter(e=>e.scrollWidth>e.clientWidth+2 && e.clientWidth>0).map(e=>({tag:e.tagName,width:e.clientWidth,scrollWidth:e.scrollWidth,overflow:getComputedStyle(e).overflowX})).slice(0,30)")
  receipt["narrow_body_text"]=page.locator("body").inner_text()
  page.screenshot(path=str(OUT/"narrow.png"),full_page=True)
  check("page exceptions",receipt["page_errors"],[])
  check("browser console errors",receipt["browser_console_errors"],[])
  check("no page external requests",[u for u in receipt["requests"] if u!=inputs["typed.html"].as_uri()],[])
  context.close();context=None;closed_safely=True
 receipt["accepted"]=True
except BaseException:receipt["error"]=traceback.format_exc()
finally:
 if context is not None:
  try:context.close();closed_safely=True;receipt["context_closed_after_error"]=True
  except BaseException:receipt["accepted"]=False;receipt["context_close_error"]=traceback.format_exc()
 receipt["after"]={name:ident(p) for name,p in inputs.items()}
 if receipt["before"]!=receipt["after"]:receipt["accepted"]=False;receipt["custody_error"]="inputs changed"
 if closed_safely and profile.exists() and not profile.is_symlink() and profile.parent==OUT:
  try:shutil.rmtree(profile);receipt["owned_profile_removed"]=True
  except BaseException:receipt["accepted"]=False;receipt["profile_cleanup_error"]=traceback.format_exc()
 receipt["closed_safely"]=closed_safely
 if not closed_safely:receipt["accepted"]=False;receipt["profile_retained_for_recovery"]=True
 receipt["finished"]=datetime.datetime.now(datetime.timezone.utc).isoformat()
 with (OUT/"receipt.json").open("xb") as f:f.write((json.dumps(receipt,sort_keys=True,ensure_ascii=True,indent=2)+"\n").encode())
 print(json.dumps({"accepted":receipt["accepted"],"checks":len(receipt["checks"]),"input_preserved":receipt["before"]==receipt["after"],"error":receipt.get("error")}))
raise SystemExit(0 if receipt["accepted"] else 1)
