#!/usr/bin/env python3
"""Build one reviewed offline comparison bundle from explicit pinned inputs."""
import argparse, hashlib, json, pathlib, stat, subprocess, sys, unicodedata, zipfile
def sha(data):return hashlib.sha256(data).hexdigest()
def valid(name):
    return isinstance(name,str) and name and not name.startswith("/") and "\\" not in name and ":" not in name and name==unicodedata.normalize("NFC",name) and all(p not in ("",".","..") for p in name.split("/"))
def regular(path):
    return not path.is_symlink() and not getattr(path,"is_junction",lambda:False)() and stat.S_ISREG(path.stat().st_mode)
def read(path):
    if not regular(path):raise ValueError("Not regular: "+str(path))
    return path.read_bytes()
def json_bytes(value):return (json.dumps(value,indent=2,sort_keys=True)+"\n").encode()
p=argparse.ArgumentParser(description=__doc__)
p.add_argument("--inputs",type=pathlib.Path,required=True);p.add_argument("--index",type=pathlib.Path,required=True)
p.add_argument("--readme",type=pathlib.Path,required=True);p.add_argument("--verifier",type=pathlib.Path,required=True)
p.add_argument("--stage",type=pathlib.Path,required=True);p.add_argument("--output",type=pathlib.Path,required=True)
args=p.parse_args()
if args.stage.exists() or args.stage.is_symlink() or args.output.exists() or args.output.is_symlink():raise SystemExit("Refusing occupied output/stage")
inputs_raw=read(args.inputs);config=json.loads(inputs_raw)
if config["format"]!="fanout.offline-comparison.inputs/1" or config["status"]!="READY_FOR_ARCHIVE":raise SystemExit("Reviewed final configuration required")
files={};origins=[]
for row in config["files"]:
    name=row["name"]
    if not valid(name) or name in files:raise ValueError("Unsafe/duplicate input name")
    path=pathlib.Path(row["path"]);body=read(path)
    if len(body)!=row["expectedBytes"] or sha(body)!=row["expectedSHA256"]:raise ValueError("Input pin mismatch: "+name)
    files[name]=body;origins.append((path,body))
extra={"INDEX.json":read(args.index),"README.md":read(args.readme),"verify-package.py":read(args.verifier),"build-package.py":read(pathlib.Path(__file__)),"PACKAGING-INPUTS.json":inputs_raw}
if set(extra)&set(files):raise ValueError("Reserved packaging name collision")
files.update(extra)
if len(files)!=len({n.casefold() for n in files}):raise ValueError("Case-fold collision")
index=json.loads(files["INDEX.json"])
if index["status"]!="READY_FOR_ARCHIVE" or index["functionalCoverage"]["independentStatus"]!="PASS":raise ValueError("Final independent qualification required")
rows=[{"path":name,"bytes":len(body),"sha256":sha(body)} for name,body in sorted(files.items())]
manifest={"schema":"fanout.offline-comparison.manifest.v1","packet":args.stage.name,"source":index["source"],"files":rows,"scope":"Exact source, authored inputs and generated comparison bytes; provenance and receiving scopes are in INDEX.json."}
files["MANIFEST.json"]=json_bytes(manifest)
files["SHA256SUMS"]=("".join(sha(body)+"  "+name+"\n" for name,body in sorted(files.items()))).encode()
args.stage.mkdir()
for name,body in sorted(files.items()):
    target=args.stage/pathlib.PurePosixPath(name);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open("xb") as out:out.write(body)
    target.chmod(0o644)
result=subprocess.run([sys.executable,"-B",str(args.stage/"verify-package.py")],capture_output=True,timeout=30)
if result.returncode:raise ValueError("Fresh staged verifier failed: "+result.stderr.decode("utf-8","replace"))
with zipfile.ZipFile(args.output,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
    for name,body in sorted(files.items()):
        info=zipfile.ZipInfo(args.stage.name+"/"+name,(2026,10,13,0,0,0))
        info.create_system=3;info.external_attr=(stat.S_IFREG|0o644)<<16;info.compress_type=zipfile.ZIP_DEFLATED
        archive.writestr(info,body,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
with zipfile.ZipFile(args.output) as archive:
    expected=[args.stage.name+"/"+name for name in sorted(files)]
    if archive.namelist()!=expected or archive.testzip() is not None:raise ValueError("Archive membership/CRC mismatch")
    for name,body in files.items():
        full=args.stage.name+"/"+name
        if archive.read(full)!=body or archive.getinfo(full).external_attr>>16!=(stat.S_IFREG|0o644):raise ValueError("Archive bytes/mode mismatch")
if any(read(path)!=body for path,body in origins):raise ValueError("A source changed during packaging")
archive_bytes=read(args.output)
print(json.dumps({"status":"PASS","path":str(args.output),"bytes":len(archive_bytes),"sha256":sha(archive_bytes),"members":len(files),"payloads":len(rows),"checksums":len(files)-1,"inputFiles":len(origins),"inputsSha256":sha(inputs_raw),"indexSha256":sha(extra["INDEX.json"]),"readmeSha256":sha(extra["README.md"]),"stagedVerifier":json.loads(result.stdout),"sourceInputsUnchanged":True}))
