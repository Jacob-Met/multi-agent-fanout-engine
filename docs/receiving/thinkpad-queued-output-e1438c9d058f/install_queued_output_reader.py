"""Dated complete-source queued file-export adoption; stage leaves the alias unchanged.

No pip, wheel metadata or network. Stage, activation and withdrawal are separate,
identity-guarded phases. Keep failed versions and raw evidence; never auto-retry.
"""
from pathlib import Path
import argparse,base64,hashlib,json,os,pwd,re,shutil,socket,stat,subprocess,sys
ROOT=Path("/home/jacob/hamon-e1438c9d058f-installed-queued-output")
SOURCE=ROOT/"candidate-source"
VERSION=Path("/home/jacob/.local/share/hamon-tools/hamon-fanout-read-93c19c7fc74b-queued-output-v1")
PREVIOUS=Path("/home/jacob/.local/share/hamon-tools/hamon-fanout-read-36f83e0767cf-queued-routes-v1/hamon-fanout-read")
ALIAS=Path("/home/jacob/.local/bin/hamon-fanout-read")
PYTHON=Path("/usr/bin/python3.14")
SWITCH=ALIAS.with_name(".hamon-fanout-read-queued-output-switch-e1438c9d058f")
RESTORE=ALIAS.with_name(".hamon-fanout-read-queued-output-restore-e1438c9d058f")
COMMIT="93c19c7fc74bda6652ab00a3d03266f53cbe5c1c"
TREE="5d0f044ada289195eb427a0a7ba902adb977d61b"
ADMISSION_SHA="cc06f9c994c1ec58594f7e8709d9d6f3300a4ac3be62537948e132c099ad1fb1"
MANIFEST_SHA="695ee10a5c6af5cb365f4d37d8e25ebcf82ecc87d6694f82cdd4d2b90911afcd"
WRAPPER_SHA="8b946c96278c0d02790c4b67f8966f76a1ec507d62656f4694a2547b7b48022e"
ORIGINAL_SHA="2d5d69be8d75a105ba98c405ee9ce2f89847ca39480b6d68455b87501bb5008d"
def require(value,message):
    if not value:raise RuntimeError(message)
def fields(s):
    return {key:getattr(s,"st_"+key) for key in ("dev","ino","mode","uid","gid","mtime_ns","size")}
def pins(data):
    return {"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"git":hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()}
def ordinary_parents(path):
    require(path.is_absolute(),"absolute path required")
    for parent in path.parents:require(stat.S_ISDIR(parent.lstat().st_mode),"nonordinary parent: "+str(parent))
def read(path):
    ordinary_parents(path)
    first=path.lstat();require(stat.S_ISREG(first.st_mode) and first.st_size<=8*1024*1024,"input kind/size differs: "+str(path))
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,"rb") as f:
        opening=os.fstat(f.fileno());data=f.read(8*1024*1024+1);closing=os.fstat(f.fileno())
    require(fields(first)==fields(opening)==fields(closing)==fields(path.lstat()) and len(data)==first.st_size,"input changed during read: "+str(path))
    return data,{**fields(first),**pins(data)}
def link(path):
    ordinary_parents(path);s=path.lstat();require(stat.S_ISLNK(s.st_mode),"expected symlink: "+str(path))
    return {**fields(s),"target":os.readlink(path)}
def owned_dir(path):
    ordinary_parents(path);s=path.lstat()
    require(stat.S_ISDIR(s.st_mode) and s.st_uid==s.st_gid==1000,"expected owned directory: "+str(path))
    return fields(s)
def write_new(path,data,mode=0o600):
    ordinary_parents(path)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
    with os.fdopen(fd,"wb") as f:f.write(data);f.flush();os.fsync(f.fileno())
def record(path,value):
    write_new(path,(json.dumps(value,indent=2)+"\n").encode())
def pinned_json(path,sha):
    data,identity=read(path);require(identity["sha256"]==sha,"pinned input differs: "+str(path));return json.loads(data)

def members(root):
    result={}
    def fail(error):raise error
    for base,dirs,files in os.walk(root,followlinks=False,onerror=fail):
        for name in sorted(dirs+files):
            p=Path(base)/name;s=p.lstat()
            row={"kind":"symlink" if stat.S_ISLNK(s.st_mode) else "directory" if stat.S_ISDIR(s.st_mode) else "file" if stat.S_ISREG(s.st_mode) else "other"}
            if row["kind"]=="symlink":row["target"]=os.readlink(p)
            result[p.relative_to(root).as_posix()]=row
    return result
def version_state():
    result={}
    for name,row in members(VERSION).items():
        p=VERSION/name
        if row["kind"]=="file":result[name]=read(p)[1]
        elif row["kind"]=="symlink":result[name]=link(p)
        elif row["kind"]=="directory":result[name]=owned_dir(p)
        else:raise RuntimeError("unexpected version member: "+name)
    return result
def identity(path):
    path=Path(path)
    if not os.path.lexists(path):return {"absent":True}
    s=path.lstat()
    if stat.S_ISREG(s.st_mode):return read(path)[1]
    if stat.S_ISLNK(s.st_mode):return link(path)
    if stat.S_ISDIR(s.st_mode):return {**owned_dir(path),"directory":True}
    raise RuntimeError("unsupported identity: "+str(path))
def tree_state(root):
    return {name:identity(root/name) for name in sorted(members(root))}
def preserved():
    original=pinned_json(ROOT/"original-refusal/receipt.json",ORIGINAL_SHA)
    expected=original["before"]
    require(expected==original["after"],"original conservation differs")
    expected["protected"].pop(str(ALIAS))
    actual={"protected":{p:identity(Path(p)) for p in expected["protected"]},"inputs":{p:identity(Path(p)) for p in expected["inputs"]},"roots":{p:tree_state(Path(p)) for p in expected["roots"]}}
    require(actual==expected,"preserved runtime/source/ledger/input identities differ")
    return actual
def source_inputs():
    names=["original-config.json","original-process.json","original-postexit.json","collect-original.py","independent-original-prelaunch.json","independent-original-review.json"]
    paths=[ROOT/n for n in names]+[SOURCE/n for n in ("hamon-fanout-read","source-manifest.json","install_queued_output_reader.py","README.md")]
    return {str(p):read(p)[1] for p in paths}
def admit():
    require(socket.gethostname()=="hamon-thinkpad" and os.getuid()==os.geteuid()==os.getgid()==os.getegid()==1000 and pwd.getpwuid(1000).pw_name=="jacob","host/account differs")
    require(Path(sys.executable).resolve()==PYTHON and sys.version_info[:3]==(3,14,4),"interpreter differs")
    a=pinned_json(ROOT/"admission.json",ADMISSION_SHA)
    pinned_json(ROOT/"frozen-independent-expectations.json","9a6a4512c199c96a7b82e5c98f72d4c5f26a293375cad5e05a9378193e157fb1")
    original=pinned_json(ROOT/"original-refusal/receipt.json",ORIGINAL_SHA)
    require(pins(read(ROOT/"original-config.json")[0])==original["config"],"original configuration differs")
    require(original["status"]=="CHARACTERIZED" and original["passed"]==8 and original["failed"]==0 and original["returncode"]==2 and original["reaped"] and original["unsupported_output_observed"],"original refusal differs")
    require(tree_state(ROOT/"original-refusal")=={**original["output_files"],"receipt.json":identity(ROOT/"original-refusal/receipt.json")},"original streams/membership differ")
    manifest=pinned_json(SOURCE/"source-manifest.json",MANIFEST_SHA)
    require(manifest["commit"]==COMMIT and manifest["tree"]==TREE and len(manifest["modules"])==20,"coherent source differs")
    require(set(manifest["modules"])==set(a["old_manifest"]["modules"]),"old/new module membership differs")
    require([name for name in manifest["modules"] if manifest["modules"][name]["git"]!=a["old_manifest"]["modules"][name]["git"]]==["fanout_engine/plan.py","fanout_engine/queued_routes.py","fanout_engine/review.py"],"attributed module delta differs")
    for name,want in manifest["modules"].items():
        require(name.startswith("fanout_engine/") and len(Path(name).parts)==2 and name.endswith(".py"),"module path")
        data,_=read(ROOT/"source"/name)
        require(pins(data)=={k:want[k] for k in ("bytes","sha256","git")} and want["mode"]=="100644","source module differs: "+name)
    wrapper,wi=read(SOURCE/"hamon-fanout-read")
    require(wi["sha256"]==WRAPPER_SHA,"wrapper differs")
    require(a["alias"]["target"]==str(PREVIOUS) and a["alias"]["ino"]==453432,"old alias authority differs")
    require(identity(PYTHON)==a["python"] and a["python"]["sha256"]=="52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41","canonical interpreter differs")
    owned_dir(ROOT);owned_dir(SOURCE);preserved()
    return a,manifest,wrapper
def observe(folder,label,argv,expected_code,stdout_rule,stderr_rule,timeout=15):
    row={"label":label,"argv":[str(x) for x in argv],"expected_exit":expected_code,"timeout_seconds":timeout,"post_kill_wait_seconds":3,"environment":"inherited env=None; values not recorded"}
    child=None
    try:
        with (folder/(label+".stdout.bin")).open("xb") as out,(folder/(label+".stderr.bin")).open("xb") as err:
            child=subprocess.Popen(row["argv"],cwd=ROOT,env=None,stdin=subprocess.DEVNULL,stdout=out,stderr=err);row["pid"]=child.pid
            try:child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                row["timed_out"]=True;child.kill()
                try:child.wait(timeout=3)
                except subprocess.TimeoutExpired:row["post_kill_wait_timeout"]=True
        row.update(returncode=child.poll(),reaped=child.returncode is not None,known_pid_present=Path("/proc/"+str(child.pid)).exists())
    except BaseException as exc:row["receiving_error"]=repr(exc)
    out=(folder/(label+".stdout.bin")).read_bytes() if (folder/(label+".stdout.bin")).exists() else b""
    err=(folder/(label+".stderr.bin")).read_bytes() if (folder/(label+".stderr.bin")).exists() else b""
    row.update(stdout=pins(out),stderr=pins(err))
    row["accepted"]=bool(row.get("returncode")==expected_code and row.get("reaped") and not row.get("known_pid_present") and not any(row.get(k) for k in ("timed_out","post_kill_wait_timeout","receiving_error")) and stdout_rule(out) and stderr_rule(err))
    record(folder/(label+".json"),row)
    require(row["accepted"],"native observation refused: "+label)
    return row
def embedded(page,golden):
    links=re.findall(rb'<a[^>]*download="saved-inspection-comparison.json"[^>]*href="data:application/json;base64,([A-Za-z0-9+/=]+)"',page)
    require(len(links)==1 and base64.b64decode(links[0],validate=True)==golden,"HTML sole exact native download differs")
def expected_outputs():
    return (read(ROOT/"inputs/expected-queued.json")[0],read(ROOT/"inputs/expected-comparison.html")[0],read(ROOT/"inputs/expected-comparison.json")[0])
def queued_args(a):
    return ["queued-routes","--database",a["database"],"--project",a["project"],"--routes",ROOT/"inputs/routes.json"]
def stage():
    a,manifest,wrapper=admit();before=preserved();inputs=source_inputs();env=dict(os.environ)
    require(link(ALIAS)==a["alias"] and shutil.which(ALIAS.name)==str(ALIAS),"old alias/PATH differs")
    for p in (VERSION,ROOT/"stage",ROOT/"staged-receipt.json",ROOT/"stage-failed.json"):require(not os.path.lexists(p),"occupied stage path: "+str(p))
    folder=ROOT/"stage";folder.mkdir(mode=0o700);VERSION.mkdir(mode=0o700)
    try:
        setup=observe(folder,"setup-venv",[PYTHON,"-I","-B","-m","venv","--without-pip",VERSION/"venv"],0,lambda b:b==b"",lambda b:b==b"",60)
        py=VERSION/"venv/bin/python";require(py.resolve()==PYTHON and identity(PYTHON)==a["python"],"new interpreter referent differs")
        require("target" in link(py),"new interpreter entry is not the expected symlink")
        cfg=read(VERSION/"venv/pyvenv.cfg")[0];require(b"include-system-site-packages = false" in cfg,"system site packages enabled")
        site=VERSION/"venv/lib/python3.14/site-packages"
        require(owned_dir(site) and not list(site.iterdir()),"new site-packages not empty")
        (site/"fanout_engine").mkdir(mode=0o700)
        for name in manifest["modules"]:write_new(site/name,read(ROOT/"source"/name)[0],0o644)
        write_new(VERSION/"source-manifest.json",read(SOURCE/"source-manifest.json")[0])
        write_new(VERSION/"hamon-fanout-read",wrapper,0o755)
        require(set(members(site))=={"fanout_engine"}|set(manifest["modules"]),"deployed complete source set differs")
        for name,want in manifest["modules"].items():
            data,row=read(site/name);require(pins(data)=={k:want[k] for k in ("bytes","sha256","git")} and stat.S_IMODE(row["mode"])==0o644,"deployed module differs: "+name)
        runtime_before=version_state();queued,page,golden=expected_outputs();embedded(page,golden)
        command=VERSION/"hamon-fanout-read";args=queued_args(a)
        rows=[observe(folder,"queued-default",[command,*args],0,lambda b:b==queued,lambda b:b==b"")]
        output=folder/"exported-queued.json"
        rows.append(observe(folder,"queued-file",[command,*args,"--output",output],0,lambda b:b==b"",lambda b:b==b""))
        require(read(output)[0]==queued,"new queued JSON differs");output_identity=read(output)[1]
        rows.append(observe(folder,"queued-occupied",[command,*args,"--output",output],1,lambda b:b==b"",lambda b:b.startswith(b"fanout queued routes: cannot write report: ") and b.endswith(b" (output: "+str(output).encode()+b")\n") and b"Traceback" not in b))
        require(read(output)[1]==output_identity,"occupied queued output changed")
        rows.append(observe(folder,"comparison-html",[command,"compare-inspections","--first",ROOT/"inputs/first.json","--second",ROOT/"inputs/second.json","--format","html"],0,lambda b:b==page,lambda b:b==b""))
        embedded(read(folder/"comparison-html.stdout.bin")[0],golden)
        after=preserved();runtime_after=version_state()
        require(before==after and source_inputs()==inputs and runtime_before==runtime_after and link(ALIAS)==a["alias"] and dict(os.environ)==env,"stage preservation failed")
        record(ROOT/"staged-receipt.json",{"phase":"staged","source_commit":COMMIT,"source_tree":TREE,"source_manifest":read(VERSION/"source-manifest.json")[1],"old_alias":a["alias"],"before":before,"after":after,"source_inputs":inputs,"runtime_before":runtime_before,"runtime_after":runtime_after,"interpreter_entry":link(py),"interpreter_referent":identity(PYTHON),"setup":setup,"observations":rows,"exported_queued":output_identity,"environment_unchanged":True,"all_checks_passed":True})
    except BaseException as exc:
        record(ROOT/"stage-failed.json",{"error":repr(exc),"observed_alias":link(ALIAS),"disposition":"Keep partial version, streams and files. No automatic retry/cleanup/activation."});raise
    print(json.dumps({"phase":"staged","cases":len(rows),"setup_cases":1,"alias_unchanged":True,"receipt":str(ROOT/"staged-receipt.json")}))
def accepted_stage():
    receipt=json.loads(read(ROOT/"staged-receipt.json")[0])
    require(receipt["phase"]=="staged" and receipt["all_checks_passed"] and receipt["source_commit"]==COMMIT and receipt["source_tree"]==TREE,"stage not accepted")
    require(receipt["before"]==receipt["after"]==preserved() and receipt["source_inputs"]==source_inputs(),"stage source/protected custody differs")
    require(receipt["runtime_before"]==receipt["runtime_after"]==version_state(),"staged complete version changed")
    require(receipt["interpreter_entry"]==link(VERSION/"venv/bin/python") and receipt["interpreter_referent"]==identity(PYTHON),"staged interpreter entry/referent differs")
    labels=["queued-default","queued-file","queued-occupied","comparison-html"]
    require([r["label"] for r in receipt["observations"]]==labels and [r["returncode"] for r in receipt["observations"]]==[0,0,1,0],"stage observations differ")
    for row in [receipt["setup"],*receipt["observations"]]:
        require(row["accepted"] and row["reaped"] and not row.get("known_pid_present") and not any(row.get(k) for k in ("timed_out","post_kill_wait_timeout","receiving_error")),"stage child refused")
        for stream in ("stdout","stderr"):require(pins(read(ROOT/"stage"/(row["label"]+"."+stream+".bin"))[0])==row[stream],"stage raw stream differs")
    require(read(ROOT/"stage/exported-queued.json")[1]==receipt["exported_queued"],"staged export differs")
    return receipt
def activate():
    a,_,_=admit();receipt=accepted_stage();before=preserved();env=dict(os.environ)
    require(link(ALIAS)==a["alias"]==receipt["old_alias"] and shutil.which(ALIAS.name)==str(ALIAS),"old alias/PATH drift")
    for p in (SWITCH,RESTORE,ROOT/"installed",ROOT/"installation-receipt.json",ROOT/"activation-failed.json",ROOT/"withdrawal-receipt.json"):require(not os.path.lexists(p),"prior activation artifact: "+str(p))
    folder=ROOT/"installed";folder.mkdir(mode=0o700);os.symlink(str(VERSION/"hamon-fanout-read"),SWITCH);new_alias=link(SWITCH);switched=False
    try:
        require(link(ALIAS)==a["alias"] and link(SWITCH)==new_alias and version_state()==receipt["runtime_after"],"switch inputs drift")
        os.replace(SWITCH,ALIAS);switched=True
        require(link(ALIAS)==new_alias and shutil.which(ALIAS.name)==str(ALIAS),"actual alias/PATH differs")
        output=folder/"queued-routes.json"
        row=observe(folder,"queued-inherited",["/usr/bin/env","hamon-fanout-read",*queued_args(a),"--output",output],0,lambda b:b==b"",lambda b:b==b"")
        queued,_,_=expected_outputs();require(read(output)[0]==queued,"installed queued JSON differs")
        after=preserved()
        require(after==before and version_state()==receipt["runtime_after"] and source_inputs()==receipt["source_inputs"] and link(ALIAS)==new_alias and dict(os.environ)==env,"installed preservation failed")
        record(ROOT/"installation-receipt.json",{"phase":"installed","source_commit":COMMIT,"source_tree":TREE,"old_alias":a["alias"],"alias":new_alias,"before":before,"after":after,"runtime":version_state(),"source_inputs":source_inputs(),"observation":row,"queued_json":read(output)[1],"environment_unchanged":True,"all_checks_passed":True})
    except BaseException as exc:
        result={"error":repr(exc),"switch_returned":switched,"expected_new_alias":new_alias,"disposition":"No automatic rollback/retry. Inspect actual alias and retained phase/version records."}
        try:result["observed_alias"]=link(ALIAS)
        except BaseException as inspection_error:result["inspection_error"]=repr(inspection_error)
        record(ROOT/"activation-failed.json",result);raise
    print(json.dumps({"phase":"installed","alias":new_alias,"queued_json":str(output)}))
def withdraw():
    a,_,_=admit();stage_record=accepted_stage();installed=json.loads(read(ROOT/"installation-receipt.json")[0])
    require(installed["phase"]=="installed" and installed["all_checks_passed"] and installed["old_alias"]==a["alias"],"installed receipt differs")
    require(link(ALIAS)==installed["alias"] and version_state()==installed["runtime"]==stage_record["runtime_after"],"actual installed version differs")
    require(not os.path.lexists(RESTORE) and not os.path.lexists(ROOT/"withdrawal-receipt.json"),"withdrawal already exists")
    before=preserved();os.symlink(str(PREVIOUS),RESTORE);restored=link(RESTORE)
    require(link(ALIAS)==installed["alias"] and link(RESTORE)==restored,"withdrawal inputs drift")
    os.replace(RESTORE,ALIAS)
    require(link(ALIAS)==restored and preserved()==before and version_state()==installed["runtime"],"withdrawal readback differs")
    record(ROOT/"withdrawal-receipt.json",{"phase":"withdrawn","restored_alias":restored,"old_target_preserved":str(PREVIOUS),"new_version_retained":str(VERSION),"note":"New symlink inode restores the prior queued/HTML target; no version bytes removed."})
    print(json.dumps({"phase":"withdrawn","alias":restored}))
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("phase",choices=("stage","activate","withdraw"));args=parser.parse_args()
    {"stage":stage,"activate":activate,"withdraw":withdraw}[args.phase]()
if __name__=="__main__":main()
