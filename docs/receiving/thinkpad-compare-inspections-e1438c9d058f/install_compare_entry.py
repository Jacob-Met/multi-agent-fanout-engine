"""Dated wrapper-only route addition; staging never changes the active alias.

Adapted from the guarded PR102 receiving pattern, retaining its prior version.
Activation and withdrawal are explicit separate phases. Failures do not retry or
automatically roll back; inspect the actual alias and retained records first.
"""
from pathlib import Path
import argparse,hashlib,json,os,pwd,shutil,socket,stat,subprocess,sys

ROOT=Path("/home/jacob/hamon-e1438c9d058f-installed-comparison")
SOURCE=ROOT/"candidate-source-v2"
OLD=Path("/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1")
PREVIOUS=Path("/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1-blockers-v1/hamon-fanout-read")
VERSION=Path("/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1-compare-inspections-v2")
ALIAS=Path("/home/jacob/.local/bin/hamon-fanout-read")
PYTHON=Path("/usr/bin/python3.14")
SWITCH=ALIAS.with_name(".hamon-fanout-read-comparison-switch-e1438c9d058f")
RESTORE=ALIAS.with_name(".hamon-fanout-read-comparison-restore-e1438c9d058f")
ADMISSION_SHA="6a21a3fd48714e111ad3bf5d8330ba8c84fdfa7db9094b99703fe7d3a2a94ad4"
CRITERIA_SHA="3d07bf58df78839a0befb65fb441b732a6692fa8d319068af002b8f2d9587b8c"
ORIGINAL_SHA="0153d7be894bf06a5812fbe78883cfd2740e634d29c9f4512bd3ab6f57702d11"
REVIEW_SHA="f664096378bbd997307645c3cfba02e27be7f3c4532a2845dae6dacd41c0d633"
WRAPPER_SHA="9c94ad1ceae16cbba8104b4b557a32a3232075076a81d679f07e2062b0162c5e"
GOLDEN_SHA="9d403925e7a6544e7f799fc05608383a339d34d11441c725119ac05575cbdb45"

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
def package_members(a):
    root=Path(a["package"]["package"]);result={}
    def fail(error):raise error
    for base,dirs,files in os.walk(root,followlinks=False,onerror=fail):
        for name in sorted(dirs+files):
            path=Path(base)/name;s=path.lstat()
            row={"kind":"symlink" if stat.S_ISLNK(s.st_mode) else "directory" if stat.S_ISDIR(s.st_mode) else "file" if stat.S_ISREG(s.st_mode) else "other"}
            if row["kind"]=="symlink":row["target"]=os.readlink(path)
            result[path.relative_to(root).as_posix()]=row
    return result
def preserved(a):
    installed=a["installed"];result={"wrapper":read(PREVIOUS)[1],"python_identity":read(PYTHON)[1],"package_members":package_members(a)}
    for key in ("runtime","receipt_identities"):
        result[key]={name:read(Path(name))[1] for name in installed[key]}
    result["links"]={name:link(Path(name)) for name in installed["links"]}
    for key in ("original_inputs","copied_inputs"):
        result[key]={name:read(Path(name))[1] for name in a[key]}
    expected={**installed,"package_members":a["package"]["members"],"original_inputs":a["original_inputs"],"copied_inputs":a["copied_inputs"]}
    expected.pop("alias")
    require(result==expected,"preserved runtime or saved input identity differs")
    require((OLD/"venv/bin/python").resolve()==PYTHON,"private interpreter target differs")
    dirs={str(p):owned_dir(p) for p in (ROOT,SOURCE,OLD,PREVIOUS.parent,VERSION.parent,ALIAS.parent)}
    result["directory_identity"]={name:{k:row[k] for k in ("dev","ino","mode","uid","gid")} for name,row in dirs.items()}
    return result
def source_inputs():
    paths=[Path(__file__).resolve(),SOURCE/"hamon-fanout-read",SOURCE/"README.md",ROOT/"admission.json",ROOT/"frozen-independent-expectations.json",ROOT/"independent-original-review.json",ROOT/"receive-original.py",ROOT/"original-process.json",ROOT/"reservation.md",ROOT/"stage-admission.py",ROOT/"admission-process.json"]
    paths.extend(ROOT/"original-v1"/name for name in ("receipt.json","stdout.bin","stderr.bin"))
    return {str(path):read(path)[1] for path in paths}
def admit():
    require(socket.gethostname()=="hamon-thinkpad" and os.getuid()==os.geteuid()==os.getgid()==os.getegid()==1000 and pwd.getpwuid(1000).pw_name=="jacob","account/host differs")
    require(Path(sys.executable).resolve()==PYTHON and sys.version_info[:3]==(3,14,4),"interpreter differs")
    owned_dir(ROOT);owned_dir(SOURCE)
    a=pinned_json(ROOT/"admission.json",ADMISSION_SHA)
    pinned_json(ROOT/"frozen-independent-expectations.json",CRITERIA_SHA)
    pinned_json(ROOT/"independent-original-review.json",REVIEW_SHA)
    original=pinned_json(ROOT/"original-v1/receipt.json",ORIGINAL_SHA)
    require(original["status"]=="CHARACTERIZED" and original["passed"]==9 and original["failed"]==0,"original observation not characterized")
    require(original["returncode"]==2 and original["reaped"] and not original.get("timed_out"),"original refusal differs")
    require(original["before"]==original["after"] and original["inputs_before"]==original["inputs_after"],"original preservation differs")
    for name,want in original["streams"].items():require(read(ROOT/"original-v1"/name)[1]==want,"original raw stream differs")
    for name,want in original["inputs_after"].items():require(read(Path(name))[1]==want,"original receiving input differs")
    require(a["source_commit"]=="639038bb09a14b54109efd2df2e699a22484a815","qualified source differs")
    require(a["installed"]["alias"]["target"]==str(PREVIOUS),"previous wrapper target differs")
    require(len(a["installed"]["runtime"])==25 and len(a["package"]["members"])==19,"qualified membership differs")
    wrapper,wi=read(SOURCE/"hamon-fanout-read")
    require(wi["bytes"]==1426 and wi["sha256"]==WRAPPER_SHA,"new wrapper differs")
    golden,gi=read(ROOT/"inputs/expected-comparison.json")
    require(gi["bytes"]==12420 and gi["sha256"]==GOLDEN_SHA,"saved comparison oracle differs")
    preserved(a)
    return a,wrapper,golden
def observe(folder,label,argv,code,want_stdout,stderr_rule):
    p=None;out=b"";err=b"";observation={"label":label,"argv":argv,"environment":"inherited env=None; values not recorded","timeout_seconds":15,"post_kill_collect_seconds":3}
    try:
        p=subprocess.Popen(argv,cwd=ROOT,env=None,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        observation["pid"]=p.pid
        try:out,err=p.communicate(timeout=15)
        except subprocess.TimeoutExpired as error:
            out=error.output if error.output is not None else b"";err=error.stderr if error.stderr is not None else b""
            observation["timed_out"]=True;p.kill()
            try:out,err=p.communicate(timeout=3)
            except subprocess.TimeoutExpired as second:
                out=second.output if second.output is not None else error.output or b""
                err=second.stderr if second.stderr is not None else error.stderr or b""
                observation["post_kill_collect_timeout"]=True
        observation.update(returncode=p.poll(),reaped=p.returncode is not None)
    except BaseException as error:
        observation["receiving_error"]=repr(error)
    finally:
        if p is not None:
            for stream in (p.stdout,p.stderr):
                if stream is not None:stream.close()
    write_new(folder/(label+".stdout.bin"),out);write_new(folder/(label+".stderr.bin"),err)
    good=observation.get("returncode")==code and observation.get("reaped") and not any(observation.get(k) for k in ("timed_out","post_kill_collect_timeout","receiving_error")) and out==want_stdout and stderr_rule(err)
    observation.update(stdout=pins(out),stderr=pins(err),accepted=bool(good))
    record(folder/(label+".json"),observation)
    require(good,"native observation failed: "+label)
    return observation
def stage():
    a,wrapper,golden=admit();before=preserved(a);inputs=source_inputs()
    require(link(ALIAS)==a["installed"]["alias"] and shutil.which("hamon-fanout-read")==str(ALIAS),"old alias/PATH differs")
    require(not os.path.lexists(VERSION) and not os.path.lexists(ROOT/"stage-v2") and not os.path.lexists(ROOT/"staged-v2-receipt.json"),"stage already exists; inspect it")
    VERSION.mkdir(mode=0o700);write_new(VERSION/"hamon-fanout-read",wrapper,0o755)
    require(read(VERSION/"hamon-fanout-read")[0]==wrapper,"staged wrapper bytes differ")
    folder=ROOT/"stage-v2";folder.mkdir(mode=0o700)
    base=[str(VERSION/"hamon-fanout-read")];pair=["compare-inspections","--first",str(ROOT/"inputs/first.json"),"--second",str(ROOT/"inputs/second.json")]
    records=[observe(folder,"comparison",base+pair,0,golden,lambda b:b==b"")]
    output=folder/"exported-comparison.json"
    records.append(observe(folder,"new-output",base+pair+["--output",str(output)],0,b"",lambda b:b==b""))
    require(read(output)[0]==golden,"new output differs from complete native oracle");output_identity=read(output)[1]
    records.append(observe(folder,"occupied-output",base+pair+["--output",str(output)],1,b"",lambda b:b.startswith(b"fanout compare-inspections: cannot write report: ") and b.endswith(b"\n") and b"Traceback" not in b))
    require(read(output)[1]==output_identity,"occupied-output refusal modified existing report")
    records.append(observe(folder,"missing-second",base+["compare-inspections","--first",str(ROOT/"inputs/first.json")],2,b"",lambda b:b.endswith(b"error: the following arguments are required: --second\n") and b"Traceback" not in b))
    refusal=b"Use: hamon-fanout-read --help (projects, inspect, history, review, blockers, compare-inspections only)\n"
    records.append(observe(folder,"reject-dispatch",base+["dispatch"],2,b"",lambda b:b==refusal))
    help_bytes=wrapper.split(b"cat <<'FANOUT_HELP'\n",1)[1].split(b"\nFANOUT_HELP\n",1)[0]+b"\n"
    records.append(observe(folder,"help",base+["--help"],0,help_bytes,lambda b:b==b""))
    after=preserved(a);require(before==after and source_inputs()==inputs and link(ALIAS)==a["installed"]["alias"],"staging changed protected inputs")
    record(ROOT/"staged-v2-receipt.json",{"phase":"staged","source_commit":a["source_commit"],"wrapper":read(VERSION/"hamon-fanout-read")[1],"version_directory":owned_dir(VERSION),"old_alias":link(ALIAS),"before":before,"after":after,"source_inputs":inputs,"observations":records,"new_output":output_identity,"all_checks_passed":True})
    print(json.dumps({"phase":"staged","cases":len(records),"receipt":str(ROOT/"staged-v2-receipt.json"),"alias_unchanged":True}))
def accepted_stage(wrapper):
    stage=json.loads(read(ROOT/"staged-v2-receipt.json")[0])
    require(stage["phase"]=="staged" and stage["all_checks_passed"],"stage not accepted")
    require([r["label"] for r in stage["observations"]]==["comparison","new-output","occupied-output","missing-second","reject-dispatch","help"],"stage cases differ")
    require([r["returncode"] for r in stage["observations"]]==[0,0,1,2,2,0],"stage outcomes differ")
    for row in stage["observations"]:
        require(row["accepted"] and row["reaped"] and not row.get("timed_out") and not row.get("post_kill_collect_timeout") and not row.get("receiving_error"),"stage child not accepted")
        for stream in ("stdout","stderr"):require(pins(read(ROOT/"stage-v2"/(row["label"]+"."+stream+".bin"))[0])==row[stream],"stage raw stream differs")
    require(stage["before"]==stage["after"] and stage["source_inputs"]==source_inputs(),"stage source custody differs")
    require(read(ROOT/"stage-v2/exported-comparison.json")[1]==stage["new_output"],"staged file output differs")
    require(read(VERSION/"hamon-fanout-read")[0]==wrapper and read(VERSION/"hamon-fanout-read")[1]==stage["wrapper"] and owned_dir(VERSION)==stage["version_directory"],"staged version identity differs")
    return stage
def activate():
    a,wrapper,golden=admit();before=preserved(a);stage_record=accepted_stage(wrapper)
    require(link(ALIAS)==a["installed"]["alias"]==stage_record["old_alias"] and shutil.which("hamon-fanout-read")==str(ALIAS),"old alias/PATH drift")
    for path in (SWITCH,RESTORE,ROOT/"installed",ROOT/"installation-receipt.json",ROOT/"activation-failed.json",ROOT/"withdrawal-receipt.json"):
        require(not os.path.lexists(path),"prior activation artifact exists: "+str(path))
    folder=ROOT/"installed";folder.mkdir(mode=0o700)
    os.symlink(str(VERSION/"hamon-fanout-read"),SWITCH);new_alias=link(SWITCH);switched=False
    try:
        require(link(ALIAS)==a["installed"]["alias"] and link(SWITCH)==new_alias and read(VERSION/"hamon-fanout-read")[1]==stage_record["wrapper"],"switch inputs drifted")
        os.replace(SWITCH,ALIAS);switched=True
        require(link(ALIAS)==new_alias and shutil.which("hamon-fanout-read")==str(ALIAS),"installed alias/PATH differs")
        observation=observe(folder,"comparison-inherited",["/usr/bin/env","hamon-fanout-read","compare-inspections","--first",str(ROOT/"inputs/first.json"),"--second",str(ROOT/"inputs/second.json")],0,golden,lambda b:b==b"")
        after=preserved(a)
        require(after==before and source_inputs()==stage_record["source_inputs"] and link(ALIAS)==new_alias and read(VERSION/"hamon-fanout-read")[1]==stage_record["wrapper"],"installed custody differs")
        record(ROOT/"installation-receipt.json",{"phase":"installed","source_commit":a["source_commit"],"old_alias":a["installed"]["alias"],"alias":new_alias,"wrapper":stage_record["wrapper"],"before":before,"after":after,"source_inputs":source_inputs(),"observation":observation,"all_checks_passed":True})
    except BaseException as error:
        result={"phase":"activation-failed","error":repr(error),"switch_returned":switched,"expected_new_alias":new_alias,"disposition":"No automatic rollback or retry. Inspect actual alias and retained version/phase records."}
        try:result["observed_alias"]=link(ALIAS)
        except BaseException as inspection_error:result["alias_inspection_error"]=repr(inspection_error)
        record(ROOT/"activation-failed.json",result);raise
    print(json.dumps({"phase":"installed","cases":1,"receipt":str(ROOT/"installation-receipt.json"),"alias":new_alias}))
def withdraw():
    a,wrapper,_=admit();accepted_stage(wrapper)
    installed=json.loads(read(ROOT/"installation-receipt.json")[0])
    require(installed["phase"]=="installed" and installed["all_checks_passed"] and installed["old_alias"]==a["installed"]["alias"],"installed receipt differs")
    require(link(ALIAS)==installed["alias"] and read(VERSION/"hamon-fanout-read")[1]==installed["wrapper"],"installed alias/version changed; inspect it")
    require(not os.path.lexists(RESTORE) and not os.path.lexists(ROOT/"withdrawal-receipt.json"),"prior withdrawal artifact exists")
    before=preserved(a);os.symlink(str(PREVIOUS),RESTORE);restored=link(RESTORE)
    require(link(ALIAS)==installed["alias"] and link(RESTORE)==restored,"withdrawal inputs drifted")
    os.replace(RESTORE,ALIAS)
    require(link(ALIAS)==restored and preserved(a)==before,"withdrawal readback differs")
    record(ROOT/"withdrawal-receipt.json",{"phase":"withdrawn","restored_alias":restored,"previous_wrapper":read(PREVIOUS)[1],"preserved":before,"version_retained":str(VERSION),"note":"New symlink inode points to unchanged PR102 five-route wrapper; no version bytes removed."})
    print(json.dumps({"phase":"withdrawn","restored_alias":restored}))
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase",choices=("stage","activate","withdraw"))
    args=parser.parse_args();{"stage":stage,"activate":activate,"withdraw":withdraw}[args.phase]()
if __name__=="__main__":main()
