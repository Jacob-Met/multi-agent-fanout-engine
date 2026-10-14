"""Dated complete-source HTML reader adoption; stage never changes the active alias.

This source-only installation uses no pip, wheel metadata or network. Activation
and withdrawal are explicit identity-guarded phases; failures never retry or
automatically roll back. Inspect actual identities after uncertain outcomes.
"""
from pathlib import Path
import argparse,base64,hashlib,json,os,pwd,re,shutil,socket,stat,subprocess,sys
ROOT=Path("/home/jacob/hamon-e1438c9d058f-installed-html")
SOURCE=ROOT/"candidate-source"
VERSION=Path("/home/jacob/.local/share/hamon-tools/hamon-fanout-read-36f83e0767cf-html-v1")
PREVIOUS=Path("/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1-compare-inspections-v2/hamon-fanout-read")
ALIAS=Path("/home/jacob/.local/bin/hamon-fanout-read")
PYTHON=Path("/usr/bin/python3.14")
SWITCH=ALIAS.with_name(".hamon-fanout-read-html-switch-e1438c9d058f")
RESTORE=ALIAS.with_name(".hamon-fanout-read-html-restore-e1438c9d058f")
COMMIT="36f83e0767cf7088fc56cd04d07042f2b285c8d1"
TREE="30a20d82623058cfd6dc86ffb92a0b502cc493ff"
ADMISSION_SHA="8ab72525bd74dddf583e0b4f22617bb3bcf62a9e18d2f5de4fe52d09c2615e27"
MANIFEST_SHA="9267b609d304dd6c61e12a4f379bfe319af0dcdabac4814295383f90c9706d2d"
WRAPPER_SHA="457c8d7e7be0b51e5496725928d3f011096122f75d2aeb1bb1be05b2dee01c5a"
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
def protected(a):
    original=pinned_json(ROOT/"original-refusal/receipt.json","80a22cc44789b38d753082447a903644a60ab055bd1430c47a264ca6d6fd7a7d")
    expected=dict(original["after"]);expected.pop(str(ALIAS))
    result={}
    for name,want in expected.items():
        p=Path(name)
        if want is None:result[name]=None if not os.path.lexists(p) else read(p)[1]
        elif "target" in want:result[name]=link(p)
        else:result[name]=read(p)[1]
    require(result==expected,"preserved installed/source/input identities differ")
    require(members(Path(a["package"]))==a["prior_after"]["package_members"],"old package membership differs")
    require(members(ROOT/"source")==original["members_after"]["source"],"source closure membership differs")
    return result
def source_inputs():
    names=["admission.json","frozen-independent-expectations.json","admit-source-inputs.py","git-source-boundary.json","published-additions.json","source-manifest.json","admission-process.json","receive-original.py","original-process.json","adjudicate-original.py","original-adjudication.json","original-refusal/receipt.json","original-refusal/stdout.bin","original-refusal/stderr.bin"]
    paths=[ROOT/n for n in names]+[SOURCE/n for n in ("hamon-fanout-read","install_html_reader.py","source-manifest.json","README.md")]
    return {str(p):read(p)[1] for p in paths}
def admit():
    require(socket.gethostname()=="hamon-thinkpad" and os.getuid()==os.geteuid()==os.getgid()==os.getegid()==1000 and pwd.getpwuid(1000).pw_name=="jacob","host/account differs")
    require(Path(sys.executable).resolve()==PYTHON and sys.version_info[:3]==(3,14,4),"interpreter differs")
    a=pinned_json(ROOT/"admission.json",ADMISSION_SHA)
    pinned_json(ROOT/"frozen-independent-expectations.json","300ed3dc6ff2cc8dddaee61df368dfb50567c360d2854d653fd4ce6a1c126946")
    original=pinned_json(ROOT/"original-refusal/receipt.json","80a22cc44789b38d753082447a903644a60ab055bd1430c47a264ca6d6fd7a7d")
    adjudication=pinned_json(ROOT/"original-adjudication.json","b3bedc565080fc8211337d304b090bac3d410631423612a0dc92b71231e64ed4")
    require(original["status"]=="FAIL" and original["passed"]==8 and original["failed"]==1 and original["returncode"]==2 and original["reaped"],"original raw boundary differs")
    require(adjudication["status"]=="CHARACTERIZATION_ACCEPTED" and all(x["passed"] for x in adjudication["checks"]),"original diagnostic not adjudicated")
    require(original["before"]==original["after"] and original["members_before"]==original["members_after"] and original["own_before"]==original["own_after"] and original["environment_unchanged"],"original preservation differs")
    for name,want in original["streams"].items():require(read(ROOT/"original-refusal"/name)[1]==want,"original raw stream differs")
    for name,want in original["own_after"].items():require(read(Path(name))[1]==want,"original receiving input differs")
    manifest=pinned_json(SOURCE/"source-manifest.json",MANIFEST_SHA)
    require(manifest["commit"]==COMMIT and manifest["tree"]==TREE and len(manifest["modules"])==20,"coherent published source differs")
    for name,want in manifest["modules"].items():
        require(name.startswith("fanout_engine/") and len(Path(name).parts)==2 and name.endswith(".py"),"module path")
        data,_=read(ROOT/"source"/name)
        require(pins(data)=={k:want[k] for k in ("bytes","sha256","git")} and want["mode"]=="100644","published source member differs: "+name)
    wrapper,wi=read(SOURCE/"hamon-fanout-read")
    require(wi["bytes"]==1569 and wi["sha256"]==WRAPPER_SHA,"wrapper differs")
    require(a["alias"]["target"]==str(PREVIOUS),"prior version differs")
    for name,want in a["prior_after"]["directory_identity"].items():
        got=owned_dir(Path(name));require({k:got[k] for k in want}==want,"directory owner/identity differs: "+name)
    owned_dir(ROOT);owned_dir(SOURCE);protected(a)
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
        row.update(returncode=child.poll(),reaped=child.returncode is not None)
    except BaseException as exc:row["receiving_error"]=repr(exc)
    out=(folder/(label+".stdout.bin")).read_bytes() if (folder/(label+".stdout.bin")).exists() else b""
    err=(folder/(label+".stderr.bin")).read_bytes() if (folder/(label+".stderr.bin")).exists() else b""
    row.update(stdout=pins(out),stderr=pins(err))
    row["accepted"]=bool(row.get("returncode")==expected_code and row.get("reaped") and not any(row.get(k) for k in ("timed_out","post_kill_wait_timeout","receiving_error")) and stdout_rule(out) and stderr_rule(err))
    record(folder/(label+".json"),row)
    require(row["accepted"],"native observation refused: "+label)
    return row
def embedded(page,golden):
    links=re.findall(rb'<a[^>]*download="saved-inspection-comparison.json"[^>]*href="data:application/json;base64,([A-Za-z0-9+/=]+)"',page)
    require(len(links)==1 and base64.b64decode(links[0],validate=True)==golden,"HTML sole exact native download differs")
def expected_outputs():
    return (read(ROOT/"inputs/expected-comparison.json")[0],read(ROOT/"inputs/expected-comparison.html")[0],read(ROOT/"inputs/expected-blockers.json")[0])
def stage():
    a,manifest,wrapper=admit();before=protected(a);inputs=source_inputs();env=dict(os.environ)
    require(link(ALIAS)==a["alias"] and shutil.which(ALIAS.name)==str(ALIAS),"old alias/PATH differs")
    for p in (VERSION,ROOT/"stage",ROOT/"staged-receipt.json",ROOT/"stage-failed.json"):require(not os.path.lexists(p),"occupied stage path: "+str(p))
    folder=ROOT/"stage";folder.mkdir(mode=0o700);VERSION.mkdir(mode=0o700)
    try:
        setup=observe(folder,"setup-venv",[PYTHON,"-I","-B","-m","venv","--without-pip",VERSION/"venv"],0,lambda b:b==b"",lambda b:b==b"",60)
        py=VERSION/"venv/bin/python";require(py.resolve()==PYTHON,"new interpreter target differs")
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
        runtime_before=version_state();golden,page,blockers=expected_outputs();embedded(page,golden)
        command=VERSION/"hamon-fanout-read";pair=["compare-inspections","--first",ROOT/"inputs/first.json","--second",ROOT/"inputs/second.json"]
        records=[observe(folder,"default-json",[command,*pair],0,lambda b:b==golden,lambda b:b==b"")]
        records.append(observe(folder,"html-stdout",[command,*pair,"--format","html"],0,lambda b:b==page,lambda b:b==b""))
        output=folder/"exported-comparison.html"
        records.append(observe(folder,"html-new-output",[command,*pair,"--format","html","--output",output],0,lambda b:b==b"",lambda b:b==b""))
        require(read(output)[0]==page,"new HTML bytes differ");output_identity=read(output)[1];embedded(read(output)[0],golden)
        records.append(observe(folder,"html-occupied-output",[command,*pair,"--format","html","--output",output],1,lambda b:b==b"",lambda b:b.startswith(b"fanout compare-inspections: cannot write report: ") and b.endswith(b"\n") and b"Traceback" not in b))
        require(read(output)[1]==output_identity,"occupied HTML changed")
        missing=folder/"absent-input.json";refused=folder/"unused-from-missing.html"
        records.append(observe(folder,"missing-input",[command,"compare-inspections","--first",missing,"--second",ROOT/"inputs/second.json","--format","html","--output",refused],2,lambda b:b==b"",lambda b:b.startswith(b"fanout compare-inspections: cannot compare saved documents: ") and b.endswith(b"\n") and b"Traceback" not in b))
        require(not os.path.lexists(missing) and not os.path.lexists(refused),"missing input/output was created")
        records.append(observe(folder,"missing-second",[command,"compare-inspections","--first",ROOT/"inputs/first.json"],2,lambda b:b==b"",lambda b:b.startswith(b"usage: python -m fanout_engine.compare_inspections ") and b.endswith(b"error: the following arguments are required: --second\n") and b"Traceback" not in b))
        records.append(observe(folder,"reject-dispatch",[command,"dispatch"],2,lambda b:b==b"",lambda b:b==b"Use: hamon-fanout-read --help (projects, inspect, history, review, blockers, compare-inspections only)\n"))
        help_bytes=wrapper.split(b"cat <<'FANOUT_HELP'\n",1)[1].split(b"\nFANOUT_HELP\n",1)[0]+b"\n"
        records.append(observe(folder,"help",[command,"--help"],0,lambda b:b==help_bytes,lambda b:b==b""))
        db=next(Path(p) for p,v in a["database"].items() if v is not None)
        records.append(observe(folder,"blockers",[command,"blockers","--database",db,"--project","fixture-handoff-51df5b72e832"],0,lambda b:b==blockers,lambda b:b==b""))
        after=protected(a);runtime_after=version_state()
        require(before==after and source_inputs()==inputs and runtime_before==runtime_after and link(ALIAS)==a["alias"] and dict(os.environ)==env,"stage preservation failed")
        record(ROOT/"staged-receipt.json",{"phase":"staged","source_commit":COMMIT,"source_tree":TREE,"source_manifest":read(VERSION/"source-manifest.json")[1],"old_alias":a["alias"],"before":before,"after":after,"source_inputs":inputs,"runtime_before":runtime_before,"runtime_after":runtime_after,"setup":setup,"observations":records,"exported_html":output_identity,"environment_unchanged":True,"all_checks_passed":True})
    except BaseException as exc:
        record(ROOT/"stage-failed.json",{"error":repr(exc),"observed_alias":link(ALIAS),"disposition":"Keep partial version, streams and files. No automatic retry/cleanup/activation."});raise
    print(json.dumps({"phase":"staged","cases":len(records),"setup_cases":1,"alias_unchanged":True,"receipt":str(ROOT/"staged-receipt.json")}))
def accepted_stage():
    receipt=json.loads(read(ROOT/"staged-receipt.json")[0])
    require(receipt["phase"]=="staged" and receipt["all_checks_passed"] and receipt["source_commit"]==COMMIT and receipt["source_tree"]==TREE,"stage not accepted")
    require(receipt["before"]==receipt["after"] and receipt["source_inputs"]==source_inputs(),"stage source/protected custody differs")
    require(receipt["runtime_before"]==receipt["runtime_after"]==version_state(),"staged complete version changed")
    labels=["default-json","html-stdout","html-new-output","html-occupied-output","missing-input","missing-second","reject-dispatch","help","blockers"]
    require([r["label"] for r in receipt["observations"]]==labels and [r["returncode"] for r in receipt["observations"]]==[0,0,0,1,2,2,2,0,0],"stage observations differ")
    for row in [receipt["setup"],*receipt["observations"]]:
        require(row["accepted"] and row["reaped"] and not any(row.get(k) for k in ("timed_out","post_kill_wait_timeout","receiving_error")),"stage child refused")
        for stream in ("stdout","stderr"):require(pins(read(ROOT/"stage"/(row["label"]+"."+stream+".bin"))[0])==row[stream],"stage raw stream differs")
    require(read(ROOT/"stage/exported-comparison.html")[1]==receipt["exported_html"],"staged export differs")
    return receipt
def activate():
    a,_,_=admit();receipt=accepted_stage();before=protected(a);env=dict(os.environ)
    require(link(ALIAS)==a["alias"]==receipt["old_alias"] and shutil.which(ALIAS.name)==str(ALIAS),"old alias/PATH drift")
    for p in (SWITCH,RESTORE,ROOT/"installed",ROOT/"installation-receipt.json",ROOT/"activation-failed.json",ROOT/"withdrawal-receipt.json"):require(not os.path.lexists(p),"prior activation artifact: "+str(p))
    folder=ROOT/"installed";folder.mkdir(mode=0o700);os.symlink(str(VERSION/"hamon-fanout-read"),SWITCH);new_alias=link(SWITCH);switched=False
    try:
        require(link(ALIAS)==a["alias"] and link(SWITCH)==new_alias and version_state()==receipt["runtime_after"],"switch inputs drift")
        os.replace(SWITCH,ALIAS);switched=True
        require(link(ALIAS)==new_alias and shutil.which(ALIAS.name)==str(ALIAS),"actual alias/PATH differs")
        output=folder/"comparison.html"
        row=observe(folder,"html-inherited",["/usr/bin/env","hamon-fanout-read","compare-inspections","--first",ROOT/"inputs/first.json","--second",ROOT/"inputs/second.json","--format","html","--output",output],0,lambda b:b==b"",lambda b:b==b"")
        golden,page,_=expected_outputs();require(read(output)[0]==page,"installed HTML differs");embedded(page,golden)
        after=protected(a)
        require(after==before and version_state()==receipt["runtime_after"] and source_inputs()==receipt["source_inputs"] and link(ALIAS)==new_alias and dict(os.environ)==env,"installed preservation failed")
        record(ROOT/"installation-receipt.json",{"phase":"installed","source_commit":COMMIT,"source_tree":TREE,"old_alias":a["alias"],"alias":new_alias,"before":before,"after":after,"runtime":version_state(),"source_inputs":source_inputs(),"observation":row,"html":read(output)[1],"environment_unchanged":True,"all_checks_passed":True})
    except BaseException as exc:
        result={"error":repr(exc),"switch_returned":switched,"expected_new_alias":new_alias,"disposition":"No automatic rollback/retry. Inspect actual alias and retained phase/version records."}
        try:result["observed_alias"]=link(ALIAS)
        except BaseException as inspection_error:result["inspection_error"]=repr(inspection_error)
        record(ROOT/"activation-failed.json",result);raise
    print(json.dumps({"phase":"installed","alias":new_alias,"html":str(output)}))
def withdraw():
    a,_,_=admit();stage_record=accepted_stage();installed=json.loads(read(ROOT/"installation-receipt.json")[0])
    require(installed["phase"]=="installed" and installed["all_checks_passed"] and installed["old_alias"]==a["alias"],"installed receipt differs")
    require(link(ALIAS)==installed["alias"] and version_state()==installed["runtime"]==stage_record["runtime_after"],"actual installed version differs")
    require(not os.path.lexists(RESTORE) and not os.path.lexists(ROOT/"withdrawal-receipt.json"),"withdrawal already exists")
    before=protected(a);os.symlink(str(PREVIOUS),RESTORE);restored=link(RESTORE)
    require(link(ALIAS)==installed["alias"] and link(RESTORE)==restored,"withdrawal inputs drift")
    os.replace(RESTORE,ALIAS)
    require(link(ALIAS)==restored and protected(a)==before and version_state()==installed["runtime"],"withdrawal readback differs")
    record(ROOT/"withdrawal-receipt.json",{"phase":"withdrawn","restored_alias":restored,"old_target_preserved":str(PREVIOUS),"new_version_retained":str(VERSION),"note":"New symlink inode restores prior JSON-only target; no version bytes removed."})
    print(json.dumps({"phase":"withdrawn","alias":restored}))
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("phase",choices=("stage","activate","withdraw"));args=parser.parse_args()
    {"stage":stage,"activate":activate,"withdraw":withdraw}[args.phase]()
if __name__=="__main__":main()
