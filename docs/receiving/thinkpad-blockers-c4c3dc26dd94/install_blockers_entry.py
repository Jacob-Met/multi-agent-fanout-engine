"""Dated wrapper-only adoption. Stage and activate are separate reviewed phases."""
from pathlib import Path
import argparse,hashlib,json,os,pwd,shutil,socket,stat,subprocess,sys
ROOT=Path('/home/jacob/fanout-blockers-20261014-c4c3dc26dd94')
OLD=Path('/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1')
VERSION=Path('/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1-blockers-v1')
ALIAS=Path('/home/jacob/.local/bin/hamon-fanout-read')
DATABASE=Path('/home/jacob/fanout-readers-20261013-c4c3dc26dd94/stage/authored-sample.sqlite')
HISTORY=DATABASE.parent.parent/'installation-receipt.json'
PYTHON=Path('/usr/bin/python3.14')
PYTHON_SHA='52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41'
HISTORY_SHA='fbb90e0d2c3c65ad78926a59653812767ea7325d439e82fa716b262b5bf954d3'
ORIGINAL_SHA='3ab002a1f98d16e02cc705d5c541a679478ff48f5444a8db6d42b10972f1ade7'
WRAPPER_SHA='39089b99978cb9786c1db4b1a075dccfcb97628aa7732657f976f0add17488fa'
EXPECTED_SHA='bd889172f732767d08ecc1a42cd6acb9e711948473f65589c01ba28006f5882c'
SWITCH=ALIAS.with_name('.hamon-fanout-read-blockers-switch-c4c3dc26dd94')
RESTORE=ALIAS.with_name('.hamon-fanout-read-blockers-restore-c4c3dc26dd94')
def require(v,m):
    if not v:raise RuntimeError(m)
def pins(b):return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'git':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()}
def fields(s):return {'dev':s.st_dev,'ino':s.st_ino,'mode':s.st_mode,'uid':s.st_uid,'gid':s.st_gid,'mtime_ns':s.st_mtime_ns,'size':s.st_size}
def read(p):
    require(p.is_absolute(),'absolute path required')
    for parent in p.parents:require(stat.S_ISDIR(parent.lstat().st_mode),'nonordinary parent: '+str(parent))
    first=p.lstat();require(stat.S_ISREG(first.st_mode) and first.st_size<=8*1024*1024,'input kind/size differs')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        a=os.fstat(f.fileno());b=f.read(8*1024*1024+1);z=os.fstat(f.fileno())
    require(fields(first)==fields(a)==fields(z)==fields(p.lstat()) and len(b)==first.st_size,'input changed during read')
    return b,{**fields(first),**pins(b)}
def link(p):
    s=p.lstat();require(stat.S_ISLNK(s.st_mode),'expected symlink: '+str(p))
    return {**fields(s),'target':os.readlink(p)}
def owned_dir(p):
    for parent in p.parents:require(stat.S_ISDIR(parent.lstat().st_mode),'nonordinary directory ancestor')
    s=p.lstat();require(stat.S_ISDIR(s.st_mode) and s.st_uid==s.st_gid==1000,'expected owned directory: '+str(p))
    return fields(s)
def write_new(p,b,mode=0o600):
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
    with os.fdopen(fd,'wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def record(p,v):write_new(p,(json.dumps(v,indent=2)+'\n').encode())
def inputs():
    require(os.getuid()==os.geteuid()==os.getgid()==os.getegid()==1000 and pwd.getpwuid(1000).pw_name=='jacob' and socket.gethostname()=='hamon-thinkpad','account/host differs')
    require(Path(sys.executable).resolve()==PYTHON and sys.version_info[:3]==(3,14,4),'interpreter differs')
    require(read(PYTHON)[1]['sha256']==PYTHON_SHA,'Python bytes differ')
    owned_dir(ROOT)
    o,oid=read(ROOT/'original-receipt.json');require(oid['sha256']==ORIGINAL_SHA,'original receipt differs');original=json.loads(o)
    require(original['accepted_witness'] and original['original_refusal_observed'] and original['all_inputs_unchanged'],'original witness not accepted')
    require(original['runtime_before']==original['runtime_after'] and original['alias_before']==original['alias_after'] and original['database_before']==original['database_after'],'original custody differs')
    require(original['directories']==original['directories_after'] and original['venv_links']==original['venv_links_after'],'original path custody differs')
    require(original['observation']['returncode']==2 and original['observation']['reaped'] and not original['observation']['timed_out'],'original result differs')
    h,hid=read(HISTORY);require(hid['sha256']==HISTORY_SHA and hid==original['receipt'],'historical receipt differs');history=json.loads(h)
    require(history['runtime']==original['runtime_before'] and history['alias_identity']==original['alias_before'] and history['fixture']==original['database_before'],'original does not match historical installation')
    wrapper,wid=read(ROOT/'hamon-fanout-read');expected,eid=read(ROOT/'expected-blockers.json')
    require(wid['sha256']==WRAPPER_SHA and len(wrapper)==1166 and eid['sha256']==EXPECTED_SHA and len(expected)==519,'candidate input differs')
    require(len(history['runtime'])==25 and history['source_commit']=='639038bb09a14b54109efd2df2e699a22484a815','qualified runtime closure differs')
    return original,history,wrapper,expected
def preserved(original,history):
    runtime={}
    for name,want in history['runtime'].items():
        p=Path(name);require(p.is_relative_to(OLD),'runtime escapes version')
        _,got=read(p);require(got==want and got['uid']==1000,'old runtime changed: '+name);runtime[name]=got
    require(runtime[str(OLD/'venv/lib/python3.14/site-packages/fanout_engine/blockers.py')]['git']=='8cdc09f08c7096ca5313ed80ed1cef0148bb977b','blocker module differs')
    links={name:link(Path(name)) for name in original['venv_links']};require(links==original['venv_links'],'qualified interpreter links changed')
    require((OLD/'venv/bin/python').resolve()==PYTHON,'venv interpreter target differs')
    db=read(DATABASE)[1];require(db==history['fixture'],'authored database changed')
    dirs={}
    for name,want in original['directories'].items():
        got=owned_dir(Path(name));require(all(got[k]==want[k] for k in ('dev','ino','mode','uid','gid')),'directory identity changed: '+name);dirs[name]=got
    require(read(PYTHON)[1]==original['python_identity'] and read(HISTORY)[1]==original['receipt'],'Python/history identity changed')
    return {'runtime':runtime,'database':db,'venv_links':links,'directory_identity':{n:{k:r[k] for k in ('dev','ino','mode','uid','gid')} for n,r in dirs.items()}}
def source_inputs():
    return {str(p):read(p)[1] for p in (Path(__file__).resolve(),ROOT/'original-receipt.json',ROOT/'hamon-fanout-read',ROOT/'expected-blockers.json')}
def run_case(folder,label,argv,expected_exit,expected_stdout,stderr_rule):
    child=subprocess.Popen(argv,cwd=ROOT,env=None,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    timeout=False
    try:out,err=child.communicate(timeout=4)
    except subprocess.TimeoutExpired:
        timeout=True;child.kill();out,err=child.communicate()
    write_new(folder/(label+'.stdout.bin'),out);write_new(folder/(label+'.stderr.bin'),err)
    good=child.returncode==expected_exit and child.poll() is not None and not timeout and out==expected_stdout and stderr_rule(err)
    result={'label':label,'argv':argv,'environment':'inherited; values not recorded','pid':child.pid,'returncode':child.returncode,'reaped':child.poll() is not None,'timed_out':timeout,'stdout':pins(out),'stderr':pins(err),'accepted':good}
    record(folder/(label+'.json'),result);require(good,'wrapper observation failed: '+label)
    return result
def stage():
    original,history,wrapper,expected=inputs();before=preserved(original,history);input_before=source_inputs()
    require(link(ALIAS)==history['alias_identity'] and shutil.which('hamon-fanout-read')==str(ALIAS),'old alias/PATH changed')
    require(not os.path.lexists(VERSION) and not os.path.lexists(ROOT/'staged-receipt.json'),'stage already exists')
    VERSION.mkdir(mode=0o700);write_new(VERSION/'hamon-fanout-read',wrapper,0o755)
    require(read(VERSION/'hamon-fanout-read')[0]==wrapper,'version wrapper differs')
    folder=ROOT/'stage';folder.mkdir(mode=0o700)
    command=[str(VERSION/'hamon-fanout-read')]
    observations=[run_case(folder,'blockers',command+['blockers','--database',str(DATABASE),'--project','sample'],0,expected,lambda b:b==b''),
        run_case(folder,'missing-database',command+['blockers','--project','sample'],2,b'',lambda b:b.endswith(b'error: the following arguments are required: --database\n') and b'Traceback' not in b),
        run_case(folder,'reject-dispatch',command+['dispatch'],2,b'',lambda b:b==b'Use: hamon-fanout-read --help (projects, inspect, history, review, blockers only)\n')]
    after=preserved(original,history);require(before==after and source_inputs()==input_before and link(ALIAS)==history['alias_identity'],'staging changed protected inputs')
    receipt={'phase':'staged','source_commit':history['source_commit'],'wrapper':read(VERSION/'hamon-fanout-read')[1],'version_directory':owned_dir(VERSION),'old_alias':link(ALIAS),'before':before,'after':after,'source_inputs':input_before,'observations':observations,'all_checks_passed':True}
    record(ROOT/'staged-receipt.json',receipt);print(json.dumps({'phase':'staged','checks':3,'receipt':str(ROOT/'staged-receipt.json')}))
def staged(wrapper):
    r=json.loads(read(ROOT/'staged-receipt.json')[0]);require(r['phase']=='staged' and r['all_checks_passed'] and len(r['observations'])==3,'stage receipt not accepted')
    require([v['label'] for v in r['observations']]==['blockers','missing-database','reject-dispatch'] and [v['returncode'] for v in r['observations']]==[0,2,2],'stage results differ')
    require(all(v['accepted'] and v['reaped'] and not v['timed_out'] for v in r['observations']),'staged child not accepted')
    for row in r['observations']:
        for stream in ('stdout','stderr'):require(pins(read(ROOT/'stage'/(row['label']+'.'+stream+'.bin'))[0])==row[stream],'stage raw stream differs')
    require(r['before']==r['after'] and r['source_inputs']==source_inputs(),'stage input custody differs')
    require(read(VERSION/'hamon-fanout-read')[0]==wrapper and read(VERSION/'hamon-fanout-read')[1]==r['wrapper'] and owned_dir(VERSION)==r['version_directory'],'staged version identity differs')
    return r
def restore(original,history,expected_alias):
    preserved(original,history);require(link(ALIAS)==expected_alias,'alias identity changed; manual inspection required')
    require(not os.path.lexists(RESTORE),'restore path exists; inspect previous interruption')
    os.symlink(str(OLD/'hamon-fanout-read'),RESTORE);temporary=link(RESTORE)
    require(link(ALIAS)==expected_alias and link(RESTORE)==temporary,'alias/restore drift before restore')
    os.replace(RESTORE,ALIAS)
    got=link(ALIAS);require(got==temporary and got['target']==str(OLD/'hamon-fanout-read'),'restore identity differs')
    return got
def activate():
    original,history,wrapper,expected=inputs();before=preserved(original,history);stage_record=staged(wrapper)
    require(link(ALIAS)==history['alias_identity']==stage_record['old_alias'] and shutil.which('hamon-fanout-read')==str(ALIAS),'old alias/PATH drift')
    require(not os.path.lexists(SWITCH) and not os.path.lexists(RESTORE) and not os.path.lexists(ROOT/'installation-receipt.json') and not os.path.lexists(ROOT/'activation-failed.json'),'previous activation artifacts exist')
    folder=ROOT/'installed';folder.mkdir(mode=0o700)
    os.symlink(str(VERSION/'hamon-fanout-read'),SWITCH);new_alias=link(SWITCH)
    require(link(ALIAS)==history['alias_identity'] and link(SWITCH)==new_alias,'switch inputs drifted')
    # Capturing the temporary link before replace preserves a restoration identity
    # even if the immediate post-switch observation raises.
    switched=False
    try:
        os.replace(SWITCH,ALIAS);switched=True
        require(link(ALIAS)==new_alias and shutil.which('hamon-fanout-read')==str(ALIAS),'installed alias/PATH differs')
        require(read(VERSION/'hamon-fanout-read')[1]==stage_record['wrapper'],'installed wrapper differs')
        observation=run_case(folder,'blockers-inherited',['/usr/bin/env','hamon-fanout-read','blockers','--database',str(DATABASE),'--project','sample'],0,expected,lambda b:b==b'')
        after=preserved(original,history)
        require(after==before and source_inputs()==stage_record['source_inputs'] and link(ALIAS)==new_alias and read(VERSION/'hamon-fanout-read')[1]==stage_record['wrapper'],'installed custody differs')
        record(ROOT/'installation-receipt.json',{'phase':'installed','source_commit':history['source_commit'],'old_alias':history['alias_identity'],'alias':new_alias,'wrapper':stage_record['wrapper'],'before':before,'after':after,'source_inputs':source_inputs(),'observation':observation,'inherited_path':os.environ.get('PATH'),'all_checks_passed':True})
    except BaseException as exc:
        result={'phase':'activation-failed','error':repr(exc),'switch_returned':switched,'expected_new_alias':new_alias}
        try:
            actual=link(ALIAS);result['observed_alias']=actual
            if actual==new_alias:result['restored_alias']=restore(original,history,new_alias)
            else:result['disposition']='Alias does not match own new identity; left unchanged for inspection.'
        except BaseException as restore_exc:result['restore_error']=repr(restore_exc)
        record(ROOT/'activation-failed.json',result);raise
    print(json.dumps({'phase':'installed','checks':1,'receipt':str(ROOT/'installation-receipt.json'),'alias':new_alias}))
def withdraw():
    original,history,wrapper,_=inputs();staged(wrapper)
    r=json.loads(read(ROOT/'installation-receipt.json')[0]);require(r['phase']=='installed' and r['all_checks_passed'],'installed receipt differs')
    require(r['wrapper']==read(VERSION/'hamon-fanout-read')[1] and r['old_alias']==history['alias_identity'],'withdrawal source differs')
    require(not os.path.lexists(ROOT/'withdrawal-receipt.json'),'withdrawal receipt already exists; inspect prior operation')
    restored=restore(original,history,r['alias'])
    record(ROOT/'withdrawal-receipt.json',{'phase':'withdrawn','restored_alias':restored,'old_runtime':preserved(original,history),'version_retained':str(VERSION),'note':'New symlink inode points to unchanged original wrapper; no version bytes removed.'})
    print(json.dumps({'phase':'withdrawn','restored_alias':restored}))
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=['stage','activate','withdraw']);a=parser.parse_args();globals()[a.phase]()
if __name__=='__main__':main()
