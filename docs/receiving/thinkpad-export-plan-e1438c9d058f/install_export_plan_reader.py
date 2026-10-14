"""Dated wrapper-only native-plan export using the unchanged qualified runtime.

Stage, activation and withdrawal are separate guarded operations. No runtime
installation, workflow, automatic retry or rollback is performed.
"""
from pathlib import Path
import argparse,hashlib,json,os,pwd,shutil,socket,stat,subprocess,sys
ROOT=Path("/home/jacob/hamon-e1438c9d058f-installed-export-plan")
SOURCE=ROOT/"candidate-source"
VERSION=Path("/home/jacob/.local/share/hamon-tools/hamon-fanout-read-93c19c7fc74b-export-plan-v1")
RUNTIME=Path("/home/jacob/.local/share/hamon-tools/hamon-fanout-read-93c19c7fc74b-queued-output-v1")
PREVIOUS=RUNTIME/"hamon-fanout-read"
ALIAS=Path("/home/jacob/.local/bin/hamon-fanout-read")
PYTHON=Path("/usr/bin/python3.14")
SWITCH=ALIAS.with_name(".hamon-fanout-read-export-plan-switch-e1438c9d058f")
RESTORE=ALIAS.with_name(".hamon-fanout-read-export-plan-restore-e1438c9d058f")
COMMIT="93c19c7fc74bda6652ab00a3d03266f53cbe5c1c"
TREE="5d0f044ada289195eb427a0a7ba902adb977d61b"
ADMISSION_SHA="221c94d17dff1b5e41252686089576fd0f8e0921e3d1f2443207c86fa3f74069"
MANIFEST_SHA="695ee10a5c6af5cb365f4d37d8e25ebcf82ecc87d6694f82cdd4d2b90911afcd"
WRAPPER_SHA="d28f01ce8bcbac553f51480f3851371d6db4049e501bb880981d1604a4f78d03"
ORIGINAL_SHA="da5bb552f319c3adeae5640c20ab0121ea2e34da23c24222fa04c8a2cc318b84"
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
    names=["original-config.json","original-process.json","original-postexit.json","collect-original.py","independent-original-review.json"]
    paths=[ROOT/n for n in names]+[SOURCE/n for n in ("hamon-fanout-read","install_export_plan_reader.py","README.md")]
    return {str(p):read(p)[1] for p in paths}
def admit():
    require(socket.gethostname()=="hamon-thinkpad" and os.getuid()==os.geteuid()==os.getgid()==os.getegid()==1000 and pwd.getpwuid(1000).pw_name=="jacob","host/account differs")
    require(Path(sys.executable).resolve()==PYTHON and sys.version_info[:3]==(3,14,4),"interpreter differs")
    a=pinned_json(ROOT/"admission.json",ADMISSION_SHA)
    pinned_json(ROOT/"frozen-independent-expectations.json","48001f2a1db14bae4d5d89b294a511382fcea11de453f4e4f6d297ed5a6dff26")
    pinned_json(ROOT/"independent-original-review.json","e30e86b5eb6bde257bb086cf562e4d2ec2430cc88f71c74ba16ac0b6395537b2")
    original=pinned_json(ROOT/"original-refusal/receipt.json",ORIGINAL_SHA)
    require(pins(read(ROOT/"original-config.json")[0])==original["config"],"original configuration differs")
    require(original["status"]=="CHARACTERIZED" and original["passed"]==8 and original["failed"]==0 and original["returncode"]==2 and original["reaped"] and original["unsupported_route_observed"],"original refusal differs")
    require(tree_state(ROOT/"original-refusal")=={**original["output_files"],"receipt.json":identity(ROOT/"original-refusal/receipt.json")},"original streams/membership differ")
    manifest=pinned_json(ROOT/"source-manifest.json",MANIFEST_SHA)
    require(manifest["commit"]==COMMIT and manifest["tree"]==TREE and len(manifest["modules"])==20,"coherent source differs")
    require(str(RUNTIME)==a["runtime"] and tree_state(RUNTIME)==a["old_version_roots"][str(RUNTIME)],"existing runtime differs")
    for name,want in manifest["modules"].items():
        require(name.startswith("fanout_engine/") and len(Path(name).parts)==2 and name.endswith(".py"),"module path")
        data,row=read(RUNTIME/"venv/lib/python3.14/site-packages"/name)
        require(pins(data)=={k:want[k] for k in ("bytes","sha256","git")} and want["mode"]=="100644" and stat.S_IMODE(row["mode"])==0o644,"runtime module differs: "+name)
    wrapper,wi=read(SOURCE/"hamon-fanout-read");require(wi["sha256"]==WRAPPER_SHA,"wrapper differs")
    require(a["alias"]["target"]==str(PREVIOUS) and a["alias"]["ino"]==453409,"old alias authority differs")
    require(identity(PYTHON)==a["python"] and a["python"]["sha256"]=="52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41","canonical interpreter differs")
    require((RUNTIME/"venv/bin/python").resolve()==PYTHON and "target" in link(RUNTIME/"venv/bin/python"),"private interpreter entry/referent differs")
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
def expected_outputs():
    return read(ROOT/"inputs/expected-plan.json")[0],read(ROOT/"inputs/expected-comparison.json")[0]
def export_args(a):
    return ["export-plan","--database",a["database"],"--project",a["project"]]
def stage():
    a,_,wrapper=admit();before=preserved();inputs=source_inputs();env=dict(os.environ)
    require(link(ALIAS)==a["alias"] and shutil.which(ALIAS.name)==str(ALIAS),"old alias/PATH differs")
    for p in (VERSION,ROOT/"stage",ROOT/"staged-receipt.json",ROOT/"stage-failed.json"):require(not os.path.lexists(p),"occupied stage path: "+str(p))
    folder=ROOT/"stage";folder.mkdir(mode=0o700);VERSION.mkdir(mode=0o700)
    try:
        write_new(VERSION/"hamon-fanout-read",wrapper,0o755);version_before=version_state()
        require(set(version_before)=={"hamon-fanout-read"} and read(VERSION/"hamon-fanout-read")[0]==wrapper,"wrapper-only version differs")
        golden,comparison=expected_outputs();command=VERSION/"hamon-fanout-read";args=export_args(a)
        rows=[observe(folder,"plan-stdout",[command,*args],0,lambda b:b==golden,lambda b:b==b"")]
        output=folder/"exported-plan.json"
        rows.append(observe(folder,"plan-file",[command,*args,"--output",output],0,lambda b:b==b"",lambda b:b==b""))
        require(read(output)[0]==golden,"new native plan differs");output_identity=read(output)[1]
        rows.append(observe(folder,"plan-occupied",[command,*args,"--output",output],1,lambda b:b==b"",lambda b:b==b"fanout export-plan: cannot write plan: output already exists; choose a new file\n"))
        require(read(output)[1]==output_identity,"occupied plan changed")
        rows.append(observe(folder,"compare-consumer",[RUNTIME/"venv/bin/python","-I","-B","-m","fanout_engine.compare","--before",output,"--after",ROOT/"inputs/authored-plan.json"],0,lambda b:b==comparison,lambda b:b==b""))
        require(read(output)[1]==output_identity,"comparison changed exported input")
        after=preserved();version_after=version_state()
        require(before==after and source_inputs()==inputs and version_before==version_after and link(ALIAS)==a["alias"] and dict(os.environ)==env,"stage preservation failed")
        record(ROOT/"staged-receipt.json",{"phase":"staged","source_commit":COMMIT,"source_tree":TREE,"old_alias":a["alias"],"before":before,"after":after,"source_inputs":inputs,"version_before":version_before,"version_after":version_after,"observations":rows,"exported_plan":output_identity,"stage_files":tree_state(folder),"environment_unchanged":True,"all_checks_passed":True})
    except BaseException as exc:
        result={"error":repr(exc),"disposition":"Keep partial wrapper version, streams and files. No automatic retry/cleanup/activation."}
        try:result["observed_alias"]=link(ALIAS)
        except BaseException as inspection_error:result["inspection_error"]=repr(inspection_error)
        record(ROOT/"stage-failed.json",result);raise
    print(json.dumps({"phase":"staged","cases":len(rows),"alias_unchanged":True,"receipt":str(ROOT/"staged-receipt.json")}))
def accepted_stage():
    receipt=json.loads(read(ROOT/"staged-receipt.json")[0])
    require(receipt["phase"]=="staged" and receipt["all_checks_passed"] and receipt["source_commit"]==COMMIT and receipt["source_tree"]==TREE,"stage not accepted")
    require(receipt["before"]==receipt["after"]==preserved() and receipt["source_inputs"]==source_inputs(),"stage source/protected custody differs")
    require(receipt["version_before"]==receipt["version_after"]==version_state(),"staged wrapper changed")
    require(receipt["stage_files"]==tree_state(ROOT/"stage"),"stage files/membership changed")
    labels=["plan-stdout","plan-file","plan-occupied","compare-consumer"]
    require([r["label"] for r in receipt["observations"]]==labels and [r["returncode"] for r in receipt["observations"]]==[0,0,1,0],"stage observations differ")
    for row in receipt["observations"]:
        require(row["accepted"] and row["reaped"] and not row.get("known_pid_present") and not any(row.get(k) for k in ("timed_out","post_kill_wait_timeout","receiving_error")),"stage child refused")
        for stream in ("stdout","stderr"):require(pins(read(ROOT/"stage"/(row["label"]+"."+stream+".bin"))[0])==row[stream],"stage raw stream differs")
    require(read(ROOT/"stage/exported-plan.json")[1]==receipt["exported_plan"],"staged export differs")
    return receipt
def activate():
    a,_,_=admit();receipt=accepted_stage();before=preserved();env=dict(os.environ)
    require(link(ALIAS)==a["alias"]==receipt["old_alias"] and shutil.which(ALIAS.name)==str(ALIAS),"old alias/PATH drift")
    for p in (SWITCH,RESTORE,ROOT/"installed",ROOT/"installation-receipt.json",ROOT/"activation-failed.json",ROOT/"withdrawal-receipt.json"):require(not os.path.lexists(p),"prior activation artifact: "+str(p))
    folder=ROOT/"installed";folder.mkdir(mode=0o700);os.symlink(str(VERSION/"hamon-fanout-read"),SWITCH);new_alias=link(SWITCH);switched=False
    try:
        require(link(ALIAS)==a["alias"] and link(SWITCH)==new_alias and version_state()==receipt["version_after"],"switch inputs drift")
        os.replace(SWITCH,ALIAS);switched=True
        require(link(ALIAS)==new_alias and shutil.which(ALIAS.name)==str(ALIAS),"actual alias/PATH differs")
        output=folder/"recorded-plan.json"
        row=observe(folder,"plan-inherited",["/usr/bin/env","hamon-fanout-read",*export_args(a),"--output",output],0,lambda b:b==b"",lambda b:b==b"")
        golden,_=expected_outputs();require(read(output)[0]==golden,"installed native plan differs")
        after=preserved()
        require(after==before and version_state()==receipt["version_after"] and source_inputs()==receipt["source_inputs"] and link(ALIAS)==new_alias and dict(os.environ)==env,"installed preservation failed")
        record(ROOT/"installation-receipt.json",{"phase":"installed","source_commit":COMMIT,"source_tree":TREE,"old_alias":a["alias"],"alias":new_alias,"before":before,"after":after,"version":version_state(),"source_inputs":source_inputs(),"observation":row,"plan_json":read(output)[1],"environment_unchanged":True,"all_checks_passed":True})
    except BaseException as exc:
        result={"error":repr(exc),"switch_returned":switched,"expected_new_alias":new_alias,"disposition":"No automatic rollback/retry. Inspect actual alias and retained phase/version records."}
        try:result["observed_alias"]=link(ALIAS)
        except BaseException as inspection_error:result["inspection_error"]=repr(inspection_error)
        record(ROOT/"activation-failed.json",result);raise
    print(json.dumps({"phase":"installed","alias":new_alias,"plan_json":str(output)}))
def withdraw():
    a,_,_=admit();stage_record=accepted_stage();installed=json.loads(read(ROOT/"installation-receipt.json")[0])
    require(installed["phase"]=="installed" and installed["all_checks_passed"] and installed["old_alias"]==a["alias"],"installed receipt differs")
    require(link(ALIAS)==installed["alias"] and version_state()==installed["version"]==stage_record["version_after"],"actual installed version differs")
    require(not os.path.lexists(RESTORE) and not os.path.lexists(ROOT/"withdrawal-receipt.json"),"withdrawal already exists")
    before=preserved();os.symlink(str(PREVIOUS),RESTORE);restored=link(RESTORE)
    require(link(ALIAS)==installed["alias"] and link(RESTORE)==restored,"withdrawal inputs drift")
    os.replace(RESTORE,ALIAS)
    require(link(ALIAS)==restored and preserved()==before and version_state()==installed["version"],"withdrawal readback differs")
    record(ROOT/"withdrawal-receipt.json",{"phase":"withdrawn","restored_alias":restored,"old_target_preserved":str(PREVIOUS),"new_version_retained":str(VERSION),"note":"New symlink inode restores the previous seven-route wrapper; no runtime/version bytes removed."})
    print(json.dumps({"phase":"withdrawn","alias":restored}))
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("phase",choices=("stage","activate","withdraw"));args=parser.parse_args()
    {"stage":stage,"activate":activate,"withdraw":withdraw}[args.phase]()
if __name__=="__main__":main()
