"""Dated coherent-source mobile comparison adoption; inactive staging first.

No pip, network or old-version writes. Stage, activation and withdrawal are
separate identity-guarded phases. Retain failed versions and raw observations.
"""
from pathlib import Path
import argparse,base64,hashlib,json,os,pwd,re,shutil,socket,stat,subprocess,sys

ROOT=Path('/home/jacob/hamon-e1438c9d058f-installed-plan-mobile')
SOURCE=ROOT/'candidate-source-v2'
VERSION=Path('/home/jacob/.local/share/hamon-tools/hamon-fanout-read-6a7aeb622146-plan-mobile-v1')
PREVIOUS=Path('/home/jacob/.local/share/hamon-tools/hamon-fanout-read-93c19c7fc74b-plan-compare-v1/hamon-fanout-read')
OLD_PACKAGE=Path('/home/jacob/.local/share/hamon-tools/hamon-fanout-read-93c19c7fc74b-queued-output-v1/venv/lib/python3.14/site-packages/fanout_engine')
ALIAS=Path('/home/jacob/.local/bin/hamon-fanout-read')
PYTHON=Path('/usr/bin/python3.14')
SWITCH=ALIAS.with_name('.hamon-fanout-read-plan-mobile-switch-e1438c9d058f')
RESTORE=ALIAS.with_name('.hamon-fanout-read-plan-mobile-restore-e1438c9d058f')
COMMIT='6a7aeb622146979fe36bc893acb6fed368de4451'
TREE='62f50f2a44dd8729a3b45b9fa87e6b7a51a989ee'
ADMISSION_SHA='0702b26cf5860894f91339e9a48f8e0e9b86c1af336595280723c87d9b60df4f'
CRITERIA_SHA='9a731e6ae6c7a5c107c7f0e392728baf72e8552a1af6a29ee25e06bec6d1a9cf'
MANIFEST_SHA='6c055686ac4a943eb3365bf5a1f1f75975a97ab135d24359a18992872864332a'
WRAPPER_SHA='4e603fde626fc7db5a47b9c2783746f2751559b497ae7bf428a19d8d0322bd8c'
DATABASE=Path('/home/jacob/hamon-e1438c9d058f-fanout-reader-closure/candidate-course/current-start-run/retained.sqlite3')
ROUTES=Path('/home/jacob/hamon-e1438c9d058f-installed-queued-routes/inputs/routes.json')
PROJECT='fixture-handoff-51df5b72e832'

def require(value,message):
    if not value:raise RuntimeError(message)
def fields(s):
    return {key:getattr(s,'st_'+key) for key in ('dev','ino','mode','uid','gid','mtime_ns','size')}
def pins(data):
    return {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'git':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()}
def ordinary_parents(path):
    require(path.is_absolute(),'absolute path required')
    for parent in path.parents:require(stat.S_ISDIR(parent.lstat().st_mode),'nonordinary parent: '+str(parent))
def read(path):
    path=Path(path);ordinary_parents(path)
    first=path.lstat();require(stat.S_ISREG(first.st_mode) and first.st_size<=8*1024*1024,'input kind/size differs: '+str(path))
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        opening=os.fstat(f.fileno());data=f.read(8*1024*1024+1);closing=os.fstat(f.fileno())
    require(fields(first)==fields(opening)==fields(closing)==fields(path.lstat()) and len(data)==first.st_size,'input changed during read: '+str(path))
    return data,{**fields(first),**pins(data)}
def link(path):
    path=Path(path);ordinary_parents(path);s=path.lstat();require(stat.S_ISLNK(s.st_mode),'expected symlink: '+str(path))
    target=os.readlink(path);require(fields(path.lstat())==fields(s),'link changed during read')
    return {**fields(s),'target':target}
def owned_dir(path):
    ordinary_parents(path);s=path.lstat()
    require(stat.S_ISDIR(s.st_mode) and s.st_uid==s.st_gid==1000,'expected owned directory: '+str(path))
    return fields(s)
def identity(path):
    path=Path(path)
    if not os.path.lexists(path):return {'absent':True}
    s=path.lstat()
    if stat.S_ISREG(s.st_mode):return read(path)[1]
    if stat.S_ISLNK(s.st_mode):return link(path)
    if stat.S_ISDIR(s.st_mode):return {**fields(s),'directory':True}
    raise RuntimeError('unsupported identity: '+str(path))
def tree_state(root):
    root=Path(root);ordinary_parents(root);require(stat.S_ISDIR(root.lstat().st_mode),'real directory required: '+str(root))
    result={}
    def fail(error):raise error
    for base,dirs,files in os.walk(root,followlinks=False,onerror=fail):
        for name in sorted(dirs+files):
            p=Path(base)/name;result[p.relative_to(root).as_posix()]=identity(p)
            require(len(result)<=2000,'root member bound')
    return dict(sorted(result.items()))
def typed_link(path):
    p=Path(path);row=link(p);target=p.resolve(strict=True)
    return {'link':row,'resolved':str(target),'referent':identity(target)}
def version_state():return tree_state(VERSION)
def version_links():return {str(VERSION/n):typed_link(VERSION/n) for n,row in version_state().items() if 'target' in row}
def write_new(path,data,mode=0o600):
    ordinary_parents(path);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
    with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
def record(path,value):write_new(path,(json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode())
def pinned_json(path,sha):
    data,row=read(path);require(row['sha256']==sha,'pinned input differs: '+str(path));return json.loads(data)
def admission():return pinned_json(ROOT/'admission.json',ADMISSION_SHA)
def criteria():return pinned_json(ROOT/'root-frozen-expectations-v2.json',CRITERIA_SHA)
def preserved():
    a=admission();expected=a['old_state'];expected['protected'].pop(str(ALIAS))
    actual={'protected':{p:identity(p) for p in expected['protected']},'inputs':{p:identity(p) for p in expected['inputs']},'roots':{p:tree_state(p) for p in expected['roots']}}
    require(actual==expected,'preserved runtime/source/ledger/input state differs')
    selected={p:identity(p) for p in a['selected']};links={p:typed_link(p) for p in a['typed_links']}
    modules={p.name:identity(p) for p in sorted(OLD_PACKAGE.iterdir())}
    require(selected==a['selected'] and links==a['typed_links'] and modules==a['old_modules'],'selected state or typed referent differs')
    return {'state':actual,'selected':selected,'typed_links':links,'old_modules':modules}
def source_inputs():
    names=['admission.json','admission-process.json','admit-native.py','contract-before-source.md','root-frozen-expectations.json','root-frozen-expectations-v2.json','root-native-order-review.json','module-closure.json','ledger-pr112.json','ledger-pr112-receiving.json']
    paths=[ROOT/n for n in names]+[SOURCE/n for n in ('hamon-fanout-read','source-manifest.json','install_plan_mobile_reader.py','README.md')]
    paths+=sorted((ROOT/'source/fanout_engine').iterdir())
    return {str(p):read(p)[1] for p in paths}
def expected_outputs():
    expected=criteria()['expected'];result={}
    for name,row in expected.items():
        data=base64.b64decode(row['base64'],validate=True)
        require(len(data)==row['bytes'] and pins(data)['sha256']==row['sha256'],'frozen payload differs: '+name);result[name]=data
    return result
def embedded(page,golden):
    links=re.findall(rb'<a[^>]*download="plan-comparison.json"[^>]*href="data:application/json;base64,([A-Za-z0-9+/=]+)"',page)
    require(len(links)==1 and base64.b64decode(links[0],validate=True)==golden,'HTML exact native download differs')
def compare_args(a):return ['compare','--before',a['actual_pair'][0],'--after',a['actual_pair'][1]]
def queued_args():return ['queued-routes','--database',DATABASE,'--project',PROJECT,'--routes',ROUTES]
def admit():
    require(socket.gethostname()=='hamon-thinkpad' and os.getuid()==os.geteuid()==os.getgid()==os.getegid()==1000 and pwd.getpwuid(1000).pw_name=='jacob','host/account differs')
    require(Path(sys.executable).resolve()==PYTHON and sys.version_info[:3]==(3,14,4),'interpreter differs')
    a=admission();f=criteria();require(a['status']=='PASS' and a['new_version']==f['new_version']==str(VERSION) and f['target_commit']==COMMIT,'admission/criteria differs')
    require(f['alias']['identity']==a['old_state']['protected'][str(ALIAS)] and f['alias']['identity']['target']==str(PREVIOUS) and f['alias']['identity']['ino']==452713,'old alias authority differs')
    require(list(f['pair'])==a['actual_pair'] and {p:identity(p) for p in f['pair']}==f['pair'] and {p:identity(p) for p in f['queued_db']}==f['queued_db'],'selected actual inputs differ')
    manifest=pinned_json(SOURCE/'source-manifest.json',MANIFEST_SHA);rows=manifest['files']
    require(manifest['source_commit']==COMMIT and manifest['source_tree']==TREE and len(rows)==20,'coherent manifest differs')
    require({Path(row['path']).name for row in rows}==set(a['old_modules']),'old/new module membership differs')
    changed=[]
    require(set(tree_state(ROOT/'source'))=={'fanout_engine'}|{row['path'] for row in rows},'source membership differs')
    for row in rows:
        name=row['path'];require(name.startswith('fanout_engine/') and len(Path(name).parts)==2 and name.endswith('.py'),'module path')
        data,_=read(ROOT/'source'/name);require(pins(data)=={k:row[k] for k in ('bytes','sha256','git')} and row['mode']=='100644','source module differs: '+name)
        if row['git']!=a['old_modules'][Path(name).name]['git']:changed.append(name)
    require(changed==manifest['changes']==['fanout_engine/compare_html.py','fanout_engine/ledger.py'] and manifest['inherited']==18,'attributed module delta differs')
    wrapper,wi=read(SOURCE/'hamon-fanout-read');require(wi['sha256']==WRAPPER_SHA,'wrapper differs')
    require(identity(PYTHON)==a['old_state']['protected'][str(PYTHON)] and identity(PYTHON)['sha256']=='52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41','canonical interpreter differs')
    owned_dir(ROOT);owned_dir(SOURCE);preserved();values=expected_outputs();embedded(values['html'],values['default_json'])
    return a,manifest,wrapper
def observe(folder,label,argv,expected_code,stdout_rule,stderr_rule,timeout=15):
    row={'label':label,'argv':[str(x) for x in argv],'expected_exit':expected_code,'timeout_seconds':timeout,'post_kill_wait_seconds':3,'environment':'inherited env=None; values not recorded'}
    child=None
    try:
        with (folder/(label+'.stdout.bin')).open('xb') as out,(folder/(label+'.stderr.bin')).open('xb') as err:
            child=subprocess.Popen(row['argv'],cwd=ROOT,env=None,stdin=subprocess.DEVNULL,stdout=out,stderr=err);row['pid']=child.pid
            try:child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                row['timed_out']=True
                try:child.kill()
                except OSError as exc:row['kill_error']=repr(exc)
                try:child.wait(timeout=3)
                except subprocess.TimeoutExpired:row['post_kill_wait_timeout']=True
    except BaseException as exc:row['receiving_error']=repr(exc)
    if child is not None:row.update(returncode=child.poll(),reaped=child.returncode is not None,known_pid_present=Path('/proc/'+str(child.pid)).exists())
    out=read(folder/(label+'.stdout.bin'))[0] if (folder/(label+'.stdout.bin')).exists() else b''
    err=read(folder/(label+'.stderr.bin'))[0] if (folder/(label+'.stderr.bin')).exists() else b''
    row.update(stdout=pins(out),stderr=pins(err))
    row['accepted']=bool(row.get('returncode')==expected_code and row.get('reaped') and not row.get('known_pid_present') and not any(row.get(k) for k in ('timed_out','kill_error','post_kill_wait_timeout','receiving_error')) and stdout_rule(out) and stderr_rule(err))
    record(folder/(label+'.json'),row);require(row['accepted'],'native observation refused: '+label)
    return row
def observation_specs(output):
    a=admission();values=expected_outputs();command=VERSION/'hamon-fanout-read';args=compare_args(a)
    rows=[('setup-venv',[PYTHON,'-I','-B','-m','venv','--without-pip',VERSION/'venv'],0,b'',b'',60),
          ('comparison-default',[command,*args],0,values['default_json'],b'',15),
          ('comparison-html',[command,*args,'--format','html','--output',output],0,b'',b'',15),
          ('comparison-occupied',[command,*args,'--format','html','--output',output],1,b'',criteria()['stage']['occupied_stderr'].encode(),15),
          ('queued-control',[command,*queued_args()],0,values['queued'],b'',15)]
    return [{'label':label,'argv':[str(x) for x in argv],'returncode':code,'stdout':pins(out),'stderr':pins(err),'timeout_seconds':timeout} for label,argv,code,out,err,timeout in rows]
def verify_observation(row,folder,want):
    require(row['label']==want['label'] and row['argv']==want['argv'] and row['expected_exit']==row['returncode']==want['returncode'] and row['timeout_seconds']==want['timeout_seconds'] and row['post_kill_wait_seconds']==3,'saved native command/status differs')
    require(row['accepted'] and row['reaped'] and not row.get('known_pid_present') and not any(row.get(k) for k in ('timed_out','kill_error','post_kill_wait_timeout','receiving_error')),'saved native child refused')
    require(json.loads(read(folder/(row['label']+'.json'))[0])==row,'saved native process record differs')
    for stream in ('stdout','stderr'):
        require(pins(read(folder/(row['label']+'.'+stream+'.bin'))[0])==row[stream]==want[stream],'saved full raw stream differs')
def continuation_history():
    f=criteria()['continuation'];objects={};identities={}
    for name,path in [('original_config',ROOT/'stage-config.json'),('original_outer',ROOT/'stage-receiving/receipt.json'),('failure_postexit',ROOT/'stage-failure-postexit.json')]:
        data,row=read(path);require(all(row[k]==f[name][k] for k in ('bytes','sha256')),'original evidence pin differs: '+name)
        objects[name]=json.loads(data);identities[str(path)]=row
    c=objects['original_config'];raw=objects['original_outer'];post=objects['failure_postexit']
    require(raw['status']=='FAIL' and raw['passed']==raw['failed']==1 and post['status']=='FAILURE_CHARACTERIZED' and post['original_status']=='FAIL' and post['conservation'],'original failure history differs')
    require(raw['before']==raw['after']=={k:c[k] for k in ('protected','inputs','roots')},'original receiving conservation differs')
    require(post['config']==pins(read(ROOT/'stage-config.json')[0]) and post['outer_receipt']==pins(read(ROOT/'stage-receiving/receipt.json')[0]),'failure closure binding differs')
    expected={'protected':{p:v for p,v in c['protected'].items() if p!=str(ALIAS)},'inputs':c['inputs'],'roots':c['roots']}
    actual={'protected':{p:identity(p) for p in expected['protected']},'inputs':{p:identity(p) for p in expected['inputs']},'roots':{p:tree_state(p) for p in expected['roots']}}
    require(actual==expected and preserved()==c['helper_preserved'],'all original nonalias state differs')
    require({p:identity(p) for p in c['helper_source_inputs']}==c['helper_source_inputs'],'original recipe/source inputs differ')
    require(tree_state(ROOT/'stage')==post['stage_files']==raw['stage_files'] and tree_state(ROOT/'stage-receiving')==post['output_files'],'original stage/outer membership differs')
    for name,row in post['small_outputs'].items():
        data,actual_row=read(ROOT/name);require(actual_row==row['identity'] and data==base64.b64decode(row['base64'],validate=True),'original raw file differs: '+name)
    require(version_state()==f['partial_version']==post['version']==raw['version'] and version_links()==f['partial_typed_links']==post['typed_version_links'],'original complete version/typed links differ')
    require(c['old_alias']==post['old_alias']==raw['actual_alias']==f['old_alias'],'original alias records differ')
    rows=post['completed_observations'];require(rows==f['completed'] and len(rows)==3 and post['pending_observations']==f['remaining_labels']==['comparison-occupied','queued-control'],'completed/pending partition differs')
    specs=observation_specs(ROOT/'stage/exported-comparison.html');require(specs==c['observations'],'original command/stream contract differs')
    for row,want in zip(rows,specs):verify_observation(row,ROOT/'stage',want)
    values=expected_outputs();page=read(ROOT/'stage/exported-comparison.html')[0]
    require(page==values['html'] and read(ROOT/'stage/comparison-default.stdout.bin')[0]==values['default_json'],'corrected complete native HTML/JSON differs');embedded(page,values['default_json'])
    require(not os.path.lexists(ROOT/'staged-receipt.json'),'original failed course has a success receipt')
    return {'evidence':identities,'state':actual,'stage_files':post['stage_files'],'outer_files':post['output_files'],'failure':identity(ROOT/'stage-failed.json'),'completed':rows,'original_status':'FAIL'}
def save_stage_receipt(kind,before,inputs,old_alias,runtime_before,runtime_links,setup,rows,output,history=None):
    after=preserved();runtime_after=version_state()
    require(before==after and source_inputs()==inputs and runtime_before==runtime_after and runtime_links==version_links() and link(ALIAS)==old_alias,'stage preservation failed')
    roots={str(ROOT/'stage-v2'):tree_state(ROOT/'stage-v2')}
    labels=[setup['label'],*[row['label'] for row in rows]]
    row_roots={label:str(ROOT/'stage-v2') for label in labels}
    if kind=='continuation':
        require(history==continuation_history(),'original failure/version state changed')
        roots[str(ROOT/'stage')]=tree_state(ROOT/'stage')
        for label in ('setup-venv','comparison-default','comparison-html'):row_roots[label]=str(ROOT/'stage')
    record(ROOT/'staged-v2-receipt.json',{'phase':'staged','course_kind':kind,'source_commit':COMMIT,'source_tree':TREE,'source_manifest':identity(VERSION/'source-manifest.json'),'old_alias':old_alias,'before':before,'after':after,'source_inputs':inputs,'runtime_before':runtime_before,'runtime_after':runtime_after,'runtime_links':runtime_links,'setup':setup,'observations':rows,'observation_roots':row_roots,'exported_html_path':str(output),'exported_html':identity(output),'stage_roots':roots,'history':history,'environment_unchanged':True,'all_checks_passed':True})
def stage_failure(exc):
    failure={'error':repr(exc),'disposition':'Keep partial version, streams and files. No automatic retry, cleanup or activation.'}
    try:failure['observed_alias']=identity(ALIAS)
    except BaseException as error:failure['alias_error']=repr(error)
    record(ROOT/'stage-v2-failed.json',failure)
def complete_stage():
    a,_,_=admit();before=preserved();inputs=source_inputs();env=dict(os.environ);old_alias=a['old_state']['protected'][str(ALIAS)]
    history=continuation_history();runtime_before=version_state();runtime_links=version_links()
    require(link(ALIAS)==old_alias and shutil.which(ALIAS.name)==str(ALIAS),'old alias/PATH differs')
    for p in (ROOT/'stage-v2',ROOT/'staged-v2-receipt.json',ROOT/'stage-v2-failed.json',SWITCH,RESTORE):require(not os.path.lexists(p),'occupied continuation path: '+str(p))
    require(os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize>=16*1024*1024,'continuation headroom below16MiB')
    folder=ROOT/'stage-v2';folder.mkdir(mode=0o700)
    try:
        output=ROOT/'stage/exported-comparison.html';output_identity=identity(output);values=expected_outputs();command=VERSION/'hamon-fanout-read'
        rows=list(history['completed'][1:])
        rows.append(observe(folder,'comparison-occupied',[command,*compare_args(a),'--format','html','--output',output],1,lambda b:b==b'',lambda b:b==criteria()['stage']['occupied_stderr'].encode()))
        require(identity(output)==output_identity,'occupied original HTML identity changed')
        rows.append(observe(folder,'queued-control',[command,*queued_args()],0,lambda b:b==values['queued'],lambda b:b==b''))
        require(dict(os.environ)==env,'continuation environment changed')
        save_stage_receipt('continuation',before,inputs,old_alias,runtime_before,runtime_links,history['completed'][0],rows,output,history)
    except BaseException as exc:stage_failure(exc);raise
    print(json.dumps({'phase':'staged','course_kind':'continuation','new_cases':2,'retained_cases':3,'alias_unchanged':True,'receipt':str(ROOT/'staged-v2-receipt.json')}))
def stage():
    a,manifest,wrapper=admit();before=preserved();inputs=source_inputs();env=dict(os.environ);old_alias=a['old_state']['protected'][str(ALIAS)]
    require(link(ALIAS)==old_alias and shutil.which(ALIAS.name)==str(ALIAS),'old alias/PATH differs')
    for p in (VERSION,ROOT/'stage-v2',ROOT/'staged-v2-receipt.json',ROOT/'stage-v2-failed.json',SWITCH,RESTORE):require(not os.path.lexists(p),'occupied stage path: '+str(p))
    require(os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize>=128*1024*1024,'persistent staging headroom below128MiB')
    folder=ROOT/'stage-v2';folder.mkdir(mode=0o700);VERSION.mkdir(mode=0o700)
    try:
        setup=observe(folder,'setup-venv',[PYTHON,'-I','-B','-m','venv','--without-pip',VERSION/'venv'],0,lambda b:b==b'',lambda b:b==b'',60)
        py=VERSION/'venv/bin/python';require(py.resolve()==PYTHON and identity(PYTHON)==a['old_state']['protected'][str(PYTHON)],'new interpreter referent differs');link(py)
        cfg=read(VERSION/'venv/pyvenv.cfg')[0];require(b'include-system-site-packages = false' in cfg,'system site packages enabled')
        site=VERSION/'venv/lib/python3.14/site-packages';owned_dir(site);require(not list(site.iterdir()),'new site-packages not empty')
        (site/'fanout_engine').mkdir(mode=0o700)
        for row in manifest['files']:write_new(site/row['path'],read(ROOT/'source'/row['path'])[0],0o644)
        write_new(VERSION/'source-manifest.json',read(SOURCE/'source-manifest.json')[0]);write_new(VERSION/'hamon-fanout-read',wrapper,0o755)
        require(set(tree_state(site))=={'fanout_engine'}|{row['path'] for row in manifest['files']},'deployed complete source set differs')
        for row in manifest['files']:
            data,actual=read(site/row['path']);require(pins(data)=={k:row[k] for k in ('bytes','sha256','git')} and stat.S_IMODE(actual['mode'])==0o644,'deployed module differs: '+row['path'])
        runtime_before=version_state();runtime_links=version_links();values=expected_outputs();command=VERSION/'hamon-fanout-read';args=compare_args(a)
        rows=[observe(folder,'comparison-default',[command,*args],0,lambda b:b==values['default_json'],lambda b:b==b'')]
        output=folder/'exported-comparison.html'
        rows.append(observe(folder,'comparison-html',[command,*args,'--format','html','--output',output],0,lambda b:b==b'',lambda b:b==b''))
        require(read(output)[0]==values['html'],'new HTML differs');embedded(read(output)[0],values['default_json']);output_identity=identity(output)
        rows.append(observe(folder,'comparison-occupied',[command,*args,'--format','html','--output',output],1,lambda b:b==b'',lambda b:b==criteria()['stage']['occupied_stderr'].encode()))
        require(identity(output)==output_identity,'occupied HTML identity changed')
        rows.append(observe(folder,'queued-control',[command,*queued_args()],0,lambda b:b==values['queued'],lambda b:b==b''))
        require(dict(os.environ)==env,'stage environment changed')
        save_stage_receipt('fresh',before,inputs,old_alias,runtime_before,runtime_links,setup,rows,output)
    except BaseException as exc:stage_failure(exc);raise
    print(json.dumps({'phase':'staged','course_kind':'fresh','new_cases':5,'retained_cases':0,'alias_unchanged':True,'receipt':str(ROOT/'staged-v2-receipt.json')}))
def accepted_stage():
    receipt=json.loads(read(ROOT/'staged-v2-receipt.json')[0])
    require(receipt['phase']=='staged' and receipt['all_checks_passed'] and receipt['source_commit']==COMMIT and receipt['source_tree']==TREE,'stage not accepted')
    require(receipt['before']==receipt['after']==preserved() and receipt['source_inputs']==source_inputs(),'stage source/protected custody differs')
    require(receipt['runtime_before']==receipt['runtime_after']==version_state() and receipt['runtime_links']==version_links(),'staged complete version differs')
    kind=receipt['course_kind'];require(kind in ('fresh','continuation'),'unknown stage provenance')
    expected_roots=[ROOT/'stage-v2'];output=ROOT/'stage-v2/exported-comparison.html'
    if kind=='continuation':
        expected_roots.append(ROOT/'stage');output=ROOT/'stage/exported-comparison.html'
        require(receipt['history']==continuation_history(),'original failed history changed')
    else:require(receipt['history'] is None,'fresh stage has continuation history')
    require(receipt['stage_roots']=={str(p):tree_state(p) for p in expected_roots},'stage membership/raw identities differ')
    rows=[receipt['setup'],*receipt['observations']];wants=observation_specs(output)
    require(len(rows)==len(wants)==5 and receipt['exported_html_path']==str(output),'stage observation count/path differs')
    roots={row['label']:str(ROOT/('stage' if kind=='continuation' and i<3 else 'stage-v2')) for i,row in enumerate(wants)}
    require(receipt['observation_roots']==roots,'stage process provenance differs')
    for row,want in zip(rows,wants):verify_observation(row,Path(roots[want['label']]),want)
    require(identity(output)==receipt['exported_html'] and read(output)[0]==expected_outputs()['html'],'staged export differs')
    return receipt
def activate():
    a,_,_=admit();receipt=accepted_stage();before=preserved();env=dict(os.environ);old_alias=a['old_state']['protected'][str(ALIAS)]
    require(link(ALIAS)==old_alias==receipt['old_alias'] and shutil.which(ALIAS.name)==str(ALIAS),'old alias/PATH drift')
    for p in (SWITCH,RESTORE,ROOT/'installed',ROOT/'installation-receipt.json',ROOT/'activation-failed.json',ROOT/'withdrawal-receipt.json'):require(not os.path.lexists(p),'prior activation artifact: '+str(p))
    folder=ROOT/'installed';folder.mkdir(mode=0o700);switched=False;new_alias=None
    try:
        os.symlink(str(VERSION/'hamon-fanout-read'),SWITCH);new_alias=link(SWITCH)
        require(link(ALIAS)==old_alias and link(SWITCH)==new_alias and version_state()==receipt['runtime_after'],'switch inputs drift')
        os.replace(SWITCH,ALIAS);switched=True
        require(link(ALIAS)==new_alias and shutil.which(ALIAS.name)==str(ALIAS),'actual alias/PATH differs')
        output=folder/'comparison.html'
        row=observe(folder,'comparison-inherited',['/usr/bin/env','hamon-fanout-read',*compare_args(a),'--format','html','--output',output],0,lambda b:b==b'',lambda b:b==b'')
        values=expected_outputs();require(read(output)[0]==values['html'],'installed HTML differs');embedded(read(output)[0],values['default_json'])
        after=preserved()
        require(after==before and version_state()==receipt['runtime_after'] and version_links()==receipt['runtime_links'] and source_inputs()==receipt['source_inputs'] and link(ALIAS)==new_alias and dict(os.environ)==env,'installed preservation failed')
        record(ROOT/'installation-receipt.json',{'phase':'installed','source_commit':COMMIT,'source_tree':TREE,'old_alias':old_alias,'alias':new_alias,'before':before,'after':after,'runtime':version_state(),'runtime_links':version_links(),'source_inputs':source_inputs(),'observation':row,'html':identity(output),'environment_unchanged':True,'all_checks_passed':True})
    except BaseException as exc:
        result={'error':repr(exc),'switch_returned':switched,'expected_new_alias':new_alias,'disposition':'No automatic rollback/retry. Inspect actual alias and retained phase/version records.'}
        try:result['observed_alias']=identity(ALIAS)
        except BaseException as inspection_error:result['inspection_error']=repr(inspection_error)
        record(ROOT/'activation-failed.json',result);raise
    print(json.dumps({'phase':'installed','alias':new_alias,'html':str(output)}))
def withdraw():
    a,_,_=admit();stage_record=accepted_stage();installed=json.loads(read(ROOT/'installation-receipt.json')[0])
    require(installed['phase']=='installed' and installed['all_checks_passed'] and installed['old_alias']==a['old_state']['protected'][str(ALIAS)],'installed receipt differs')
    require(link(ALIAS)==installed['alias'] and version_state()==installed['runtime']==stage_record['runtime_after'] and version_links()==installed['runtime_links'],'actual installed version differs')
    require(not os.path.lexists(RESTORE) and not os.path.lexists(ROOT/'withdrawal-receipt.json'),'withdrawal already exists')
    before=preserved();os.symlink(str(PREVIOUS),RESTORE);restored=link(RESTORE)
    require(link(ALIAS)==installed['alias'] and link(RESTORE)==restored,'withdrawal inputs drift');os.replace(RESTORE,ALIAS)
    require(link(ALIAS)==restored and preserved()==before and version_state()==installed['runtime'],'withdrawal readback differs')
    record(ROOT/'withdrawal-receipt.json',{'phase':'withdrawn','restored_alias':restored,'old_target_preserved':str(PREVIOUS),'new_version_retained':str(VERSION),'note':'A new symlink inode restores the prior target; no version bytes removed.'})
    print(json.dumps({'phase':'withdrawn','alias':restored}))
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('phase',choices=('stage','complete-stage','activate','withdraw'));args=parser.parse_args()
    {'stage':stage,'complete-stage':complete_stage,'activate':activate,'withdraw':withdraw}[args.phase]()
if __name__=='__main__':main()
