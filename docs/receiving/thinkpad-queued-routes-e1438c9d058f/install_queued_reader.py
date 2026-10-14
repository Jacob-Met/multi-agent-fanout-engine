"""Dated wrapper-only queued-route adoption using the existing qualified HTML runtime.

Stage does not switch the active alias or install runtime modules. Activation and
withdrawal are explicit guarded operations. Retain failed files and inspect the
actual alias after any uncertain result; no automatic retry or rollback occurs.
"""
from pathlib import Path
import argparse,hashlib,json,os,pwd,shutil,socket,stat,subprocess,sys
ROOT=Path("/home/jacob/hamon-e1438c9d058f-installed-queued-routes")
SOURCE=ROOT/"candidate-source"
VERSION=Path("/home/jacob/.local/share/hamon-tools/hamon-fanout-read-36f83e0767cf-queued-routes-v1")
RUNTIME=Path("/home/jacob/.local/share/hamon-tools/hamon-fanout-read-36f83e0767cf-html-v1")
PREVIOUS=RUNTIME/"hamon-fanout-read"
ALIAS=Path("/home/jacob/.local/bin/hamon-fanout-read")
PYTHON=Path("/usr/bin/python3.14")
SWITCH=ALIAS.with_name(".hamon-fanout-read-queued-switch-e1438c9d058f")
RESTORE=ALIAS.with_name(".hamon-fanout-read-queued-restore-e1438c9d058f")
COMMIT="36f83e0767cf7088fc56cd04d07042f2b285c8d1"
ADMISSION_SHA="f60e42f9b2cfa4d36b81414ad50ac552c979628eecf11a74dcb8425c31309d90"
CRITERIA_SHA="afc8b6cc2a57ecc8ff269cbafdf5a0d6f3512c568c3d3f2d7b7e449f0c37c01f"
ORIGINAL_SHA="2b2603836a632c043b7de7ba3a60d6f3367c1a6d45e3c8e18c47c1394c8b56c8"
CONFIG_SHA="9773bdb3fcc9a9427b1fe86042ef1f48308f0dc1851b34e0b87ee56a95e18a41"
WRAPPER_SHA="de72c2307c7bbeb5340ccfa83f94e2a2c94d90db8944a361e8145a0b82e41627"
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


def identity(path):
    if not os.path.lexists(path):return None
    s=path.lstat()
    if stat.S_ISREG(s.st_mode):return read(path)[1]
    if stat.S_ISLNK(s.st_mode):return link(path)
    return owned_dir(path)
def tree(root):
    result={}
    def fail(error):raise error
    for base,dirs,files in os.walk(root,followlinks=False,onerror=fail):
        for name in sorted(dirs+files):
            p=Path(base)/name;result[p.relative_to(root).as_posix()]=identity(p)
    return result
def source_inputs():
    names=["identity.json","source-boundary.json","admit-inputs.py","admission.json","admission-process.json","freeze-independent.py","frozen-independent-expectations.json","independent-freeze-process.json","receive-original.py","freeze-original.py","original-config.json","original-freeze-process.json","original-process.json","collect-original.py","original-postexit.json","original-postexit-process.json","independent-original-prelaunch.json","independent-original-review.json"]
    paths=[ROOT/n for n in names]+[SOURCE/n for n in ("hamon-fanout-read","install_queued_reader.py","README.md")]
    return {str(p):read(p)[1] for p in paths}
def protected(cfg):
    expected=dict(cfg["protected"]);expected.pop(str(ALIAS))
    got={p:identity(Path(p)) for p in expected};require(got==expected,"protected installed/database/input identity differs");return got
def old_roots(cfg):
    got={p:tree(Path(p)) for p in cfg["roots"]};require(got==cfg["roots"],"retained versions/input membership differs");return got
def admit():
    require(socket.gethostname()=="hamon-thinkpad" and os.getuid()==os.geteuid()==os.getgid()==os.getegid()==1000 and pwd.getpwuid(1000).pw_name=="jacob","host/account differs")
    require(Path(sys.executable).resolve()==PYTHON and sys.version_info[:3]==(3,14,4),"canonical interpreter differs")
    a=pinned_json(ROOT/"admission.json",ADMISSION_SHA);criteria=pinned_json(ROOT/"frozen-independent-expectations.json",CRITERIA_SHA)
    cfg=pinned_json(ROOT/"original-config.json",CONFIG_SHA);original=pinned_json(ROOT/"original-refusal/receipt.json",ORIGINAL_SHA)
    require(original["status"]=="CHARACTERIZED" and original["passed"]==12 and original["failed"]==0 and original["returncode"]==2 and original["reaped"],"original refusal differs")
    require(original["before"]==original["after"]==cfg["protected"] and original["roots_before"]==original["roots_after"]==cfg["roots"] and original["inputs_before"]==original["inputs_after"]==cfg["inputs"],"original conservation differs")
    for stream in ("stdout","stderr"):require(pins(read(ROOT/"original-refusal"/(stream+".bin"))[0])==original[stream],"original raw stream differs")
    for name,want in cfg["inputs"].items():require(identity(Path(name))==want,"original input differs")
    require(identity(ROOT/"original-config.json")==original["config_after"],"original configuration identity differs")
    require(a["alias"]==cfg["old_alias"] and a["alias"]["target"]==str(PREVIOUS),"old alias binding differs")
    require(tree(RUNTIME)==a["runtime"] and len(criteria["runtime_modules"])==20,"qualified runtime differs")
    for row in criteria["runtime_modules"]:
        data,_=read(RUNTIME/"venv/lib/python3.14/site-packages"/row["path"])
        require(pins(data)["git"]==row["git"] and len(data)==row["bytes"] and row["mode"]=="100644","coherent runtime module differs")
    wrapper,wi=read(SOURCE/"hamon-fanout-read");require(wi["sha256"]==WRAPPER_SHA,"wrapper source differs")
    require(read(PYTHON)[1]["sha256"]=="52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41","interpreter bytes differ")
    owned_dir(ROOT);owned_dir(SOURCE);protected(cfg);old_roots(cfg)
    return a,cfg,wrapper
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

def expected():
    return read(ROOT/"inputs/expected-queued.json")[0],read(ROOT/"inputs/expected-comparison.html")[0]
def route_args(a):
    db=next(Path(p) for p,v in a["database"].items() if v is not None)
    return ["queued-routes","--database",db,"--project",a["project"],"--routes",ROOT/"inputs/routes.json"]
def stage():
    a,cfg,wrapper=admit();before=protected(cfg);roots=old_roots(cfg);inputs=source_inputs();env=dict(os.environ)
    require(link(ALIAS)==a["alias"] and shutil.which(ALIAS.name)==str(ALIAS),"old alias/PATH differs")
    for p in (VERSION,ROOT/"stage",ROOT/"staged-receipt.json",ROOT/"stage-failed.json"):require(not os.path.lexists(p),"occupied stage path: "+str(p))
    folder=ROOT/"stage";folder.mkdir(mode=0o700);VERSION.mkdir(mode=0o700)
    try:
        write_new(VERSION/"hamon-fanout-read",wrapper,0o755);version=tree(VERSION)
        require(set(version)=={"hamon-fanout-read"} and read(VERSION/"hamon-fanout-read")[0]==wrapper,"wrapper-only version differs")
        golden,page=expected();command=VERSION/"hamon-fanout-read";argv=route_args(a)
        rows=[observe(folder,"queued-routes",[command,*argv],0,lambda b:b==golden,lambda b:b==b"")]
        rows.append(observe(folder,"missing-routes",[command,*argv[:-2]],2,lambda b:b==b"",lambda b:b.startswith(b"usage: ") and b.endswith(b"error: the following arguments are required: --routes\n") and b"Traceback" not in b and b"\x1b" not in b))
        refusal=b"Use: hamon-fanout-read --help (projects, inspect, history, review, blockers, compare-inspections, queued-routes only)\n"
        rows.append(observe(folder,"reject-dispatch",[command,"dispatch"],2,lambda b:b==b"",lambda b:b==refusal))
        help_bytes=wrapper.split(b"cat <<'FANOUT_HELP'\n",1)[1].split(b"\nFANOUT_HELP\n",1)[0]+b"\n"
        rows.append(observe(folder,"help",[command,"--help"],0,lambda b:b==help_bytes,lambda b:b==b""))
        rows.append(observe(folder,"html-stdout",[command,"compare-inspections","--first",ROOT/"inputs/first.json","--second",ROOT/"inputs/second.json","--format","html"],0,lambda b:b==page,lambda b:b==b""))
        after=protected(cfg);after_roots=old_roots(cfg)
        require(after==before and after_roots==roots and source_inputs()==inputs and tree(VERSION)==version and link(ALIAS)==a["alias"] and dict(os.environ)==env,"stage conservation failed")
        record(ROOT/"staged-receipt.json",{"phase":"staged","runtime_source":COMMIT,"old_alias":a["alias"],"before":before,"after":after,"roots_before":roots,"roots_after":after_roots,"source_inputs":inputs,"version":version,"observations":rows,"stage_files":tree(folder),"environment_unchanged":True,"all_checks_passed":True})
    except BaseException as exc:
        result={"error":repr(exc),"disposition":"Retain failed stage/version/raw files. No activation, automatic retry or cleanup."}
        try:result["actual_alias"]=link(ALIAS)
        except BaseException as failure:result["alias_inspection_error"]=repr(failure)
        record(ROOT/"stage-failed.json",result);raise
    print(json.dumps({"phase":"staged","cases":len(rows),"alias_unchanged":True}))
def accepted_stage(cfg):
    r=json.loads(read(ROOT/"staged-receipt.json")[0])
    require(r["phase"]=="staged" and r["all_checks_passed"] and r["runtime_source"]==COMMIT,"stage not accepted")
    require(r["before"]==r["after"]==protected(cfg) and r["roots_before"]==r["roots_after"]==old_roots(cfg),"stage conservation differs")
    require(r["source_inputs"]==source_inputs() and r["version"]==tree(VERSION) and r["stage_files"]==tree(ROOT/"stage"),"staged source/version/raw custody differs")
    require([row["label"] for row in r["observations"]]==["queued-routes","missing-routes","reject-dispatch","help","html-stdout"] and [row["returncode"] for row in r["observations"]]==[0,2,2,0,0],"five stage observations differ")
    for row in r["observations"]:
        require(row["accepted"] and row["reaped"] and not any(row.get(k) for k in ("timed_out","post_kill_wait_timeout","receiving_error")),"stage child refused")
        for stream in ("stdout","stderr"):require(pins(read(ROOT/"stage"/(row["label"]+"."+stream+".bin"))[0])==row[stream],"stage raw stream differs")
    return r
def activate():
    a,cfg,_=admit();r=accepted_stage(cfg);before=protected(cfg);roots=old_roots(cfg);env=dict(os.environ)
    require(link(ALIAS)==a["alias"]==r["old_alias"] and shutil.which(ALIAS.name)==str(ALIAS),"old alias/PATH drift")
    for p in (SWITCH,RESTORE,ROOT/"installed",ROOT/"installation-receipt.json",ROOT/"activation-failed.json",ROOT/"withdrawal-receipt.json"):require(not os.path.lexists(p),"prior activation artifact: "+str(p))
    folder=ROOT/"installed";folder.mkdir(mode=0o700);os.symlink(str(VERSION/"hamon-fanout-read"),SWITCH);new_alias=link(SWITCH);switched=False
    try:
        require(link(ALIAS)==a["alias"] and link(SWITCH)==new_alias and tree(VERSION)==r["version"],"switch inputs drift")
        os.replace(SWITCH,ALIAS);switched=True
        require(link(ALIAS)==new_alias and shutil.which(ALIAS.name)==str(ALIAS),"actual alias/PATH differs")
        golden,_=expected();row=observe(folder,"queued-inherited",["/usr/bin/env","hamon-fanout-read",*route_args(a)],0,lambda b:b==golden,lambda b:b==b"")
        after=protected(cfg);after_roots=old_roots(cfg)
        require(after==before and after_roots==roots and source_inputs()==r["source_inputs"] and tree(VERSION)==r["version"] and link(ALIAS)==new_alias and dict(os.environ)==env,"installed conservation failed")
        record(ROOT/"installation-receipt.json",{"phase":"installed","runtime_source":COMMIT,"old_alias":a["alias"],"alias":new_alias,"before":before,"after":after,"roots_before":roots,"roots_after":after_roots,"version":tree(VERSION),"source_inputs":source_inputs(),"observation":row,"environment_unchanged":True,"all_checks_passed":True})
    except BaseException as exc:
        result={"error":repr(exc),"switch_returned":switched,"expected_new_alias":new_alias,"disposition":"No automatic rollback/retry. Inspect actual alias, retained version and phase records."}
        try:result["actual_alias"]=link(ALIAS)
        except BaseException as failure:result["alias_inspection_error"]=repr(failure)
        record(ROOT/"activation-failed.json",result);raise
    print(json.dumps({"phase":"installed","alias":new_alias,"native_report":str(folder/"queued-inherited.stdout.bin")}))
def withdraw():
    a,cfg,_=admit();stage_record=accepted_stage(cfg);installed=json.loads(read(ROOT/"installation-receipt.json")[0])
    require(installed["phase"]=="installed" and installed["all_checks_passed"] and installed["old_alias"]==a["alias"],"installation record differs")
    require(link(ALIAS)==installed["alias"] and tree(VERSION)==installed["version"]==stage_record["version"],"active installed version differs")
    require(not os.path.lexists(RESTORE) and not os.path.lexists(ROOT/"withdrawal-receipt.json"),"withdrawal already exists")
    before=protected(cfg);roots=old_roots(cfg);os.symlink(str(PREVIOUS),RESTORE);restored=link(RESTORE)
    require(link(ALIAS)==installed["alias"] and link(RESTORE)==restored,"withdrawal inputs drift")
    os.replace(RESTORE,ALIAS)
    require(link(ALIAS)==restored and protected(cfg)==before and old_roots(cfg)==roots and tree(VERSION)==installed["version"],"withdrawal readback differs")
    record(ROOT/"withdrawal-receipt.json",{"phase":"withdrawn","restored_alias":restored,"old_target_preserved":str(PREVIOUS),"new_version_retained":str(VERSION),"note":"A new symlink inode restores the previous HTML-capable wrapper. No version/runtime bytes removed or product replay."})
    print(json.dumps({"phase":"withdrawn","alias":restored}))
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("phase",choices=("stage","activate","withdraw"));args=parser.parse_args()
    {"stage":stage,"activate":activate,"withdraw":withdraw}[args.phase]()
if __name__=="__main__":main()
