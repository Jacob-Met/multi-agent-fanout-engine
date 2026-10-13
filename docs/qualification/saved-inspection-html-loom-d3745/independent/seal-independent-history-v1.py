from pathlib import Path
import hashlib,json,stat

ROOT=Path(__file__).resolve().parent
MIRROR=Path('/dev/shm/forge-d3745-fanout-html-review/native-mirror')
def pin(path):
    b=path.read_bytes()
    return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'git_blob':hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),'native_mode':stat.S_IMODE(path.stat().st_mode)}

names=[
 'README-independent-history.md','seal-independent-history-v1.py',
 'criteria-v1.json','prepare-original-v1.py','original-oracles.json',
 'fixtures/first.json','fixtures/second.json','fixtures/order-only.json','fixtures/mismatched.json',
 'fixtures/typed-oracle.json','fixtures/typed-oracle.stderr','fixtures/order-oracle.json','fixtures/order-oracle.stderr',
 'receive-cli-v1.py','receive-cli-v2.py',
 'receive-browser-v1.py','receive-browser-v2.py','receive-browser-v3.py','receive-browser-v4.cjs','receive-browser-v5.cjs',
 'executable-freeze-v1.json','executable-freeze-v2.json','executable-freeze-v3.json',
 'browser-adaptation-v4.json','browser-adaptation-v5.json','candidate-spec.json','harness-review.json',
 'course-v2/receipt.json','course-v2/typed.html','course-v2/order.html',
 'visual-review-v1.json','forge-adaptation-review.json','forge-result-reassessment.json','forge-mirror-receipt.json',
 'browser-initial-tool-result-v3.json','browser-initial-tool-result-v5.json','browser-final-tool-result-v5.json',
]
for n in ['default-json','explicit-json','typed-html','typed-file','occupied-output','input-output','mismatched','order-only']:
    names.extend(['course-v2/'+n+'.stdout','course-v2/'+n+'.stderr'])
files=[]
for name in names:
    p=ROOT/name
    files.append({'path':name,'source_path':str(p),'mode':'100644',**pin(p)})
native=json.loads((MIRROR/'native-identities.json').read_bytes())
for row in native['files']:
    p=MIRROR/row['path']; x=pin(p)
    assert all(x[k]==row[k] for k in ['bytes','sha256','git_blob'])
    assert x['native_mode']==row['mode']
    files.append({'path':'native/'+row['path'],'source_path':row['source_path'],'mirror_path':str(p),'mode':'100644',**x})
files.append({'path':'native/native-identities.json','source_path':str(MIRROR/'native-identities.json'),'mode':'100644',**pin(MIRROR/'native-identities.json')})
assert len(set(r['path'] for r in files))==len(files)
course=json.loads((ROOT/'course-v2/receipt.json').read_bytes())
assert course['accepted'] and len(course['checks'])==32 and all(x['passed'] for x in course['checks'])
browser=json.loads((MIRROR/'browser-v5/receipt.json').read_bytes())
assert browser['accepted'] is False and len(browser['checks'])==31
assert [x['name'] for x in browser['checks'] if not x['passed']]==['no page external requests']
assert (MIRROR/'browser-v5/downloads/saved-inspection-comparison.json').read_bytes()==(ROOT/'fixtures/typed-oracle.json').read_bytes()
result={'schema':'hamon.root.fanout-html.independent-history-inputs.v1','prefix':'docs/qualification/saved-inspection-html-loom-d3745/independent/','files':files,'scope':'Code-specific original independent receiving history for the archived Loom candidate.32/32 CLI checks passed; original v3 and v5 browser attempts failed; desktop semantic review passed; actual narrow visual gate failed. This descriptor authorizes only the explicit unchanged listed evidence and is not current product acceptance or PR97 qualification.','history':['Candidate-free criteria/original oracles and three executable freezes preceded candidate exposure. V4/v5 environment adaptations followed exposure and preserve failed v3.','Original tool-result JSON captures are connector reports preserved after execution, not separately captured native stdout/stderr files.','Native source_path and0664 modes are retained; mirror_path identifies exact custody copies. Git mode100644 expresses nonexecutable regular content.','Raw browser requests are unchanged; separate reassessment distinguishes inline font request from external network without changing original acceptance:false.','Original candidate/runtime bodies are bound by candidate-spec and original-oracles and retained separately in the author archive; none of these results qualify another source.']}
out=ROOT/'independent-publication-inputs-v1.json'
with out.open('x',encoding='utf-8',newline='\n') as f: f.write(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({'files':len(files),'payload_bytes':sum(r['bytes'] for r in files),'descriptor':pin(out)},indent=2))
