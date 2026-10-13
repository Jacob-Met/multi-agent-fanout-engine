#!/usr/bin/env python3
"""Verify this offline comparison package's complete regular-file bytes."""
import hashlib, json, pathlib, stat, sys, unicodedata
ROOT=pathlib.Path(__file__).resolve().parent
def valid(name):
    return isinstance(name,str) and name and not name.startswith("/") and "\\" not in name and ":" not in name and name==unicodedata.normalize("NFC",name) and all(p not in ("",".","..") for p in name.split("/"))
def regular(path):
    return not path.is_symlink() and not getattr(path,"is_junction",lambda:False)() and stat.S_ISREG(path.stat().st_mode)
def read(name):
    if not valid(name):raise ValueError("Unsafe path: "+str(name))
    path=ROOT/pathlib.PurePosixPath(name)
    if not regular(path):raise ValueError("Not a regular file: "+name)
    return path.read_bytes()
def sha(data):return hashlib.sha256(data).hexdigest()
try:
    manifest=json.loads(read("MANIFEST.json"));rows=manifest["files"]
    if manifest["schema"]!="fanout.offline-comparison.manifest.v1" or not rows:raise ValueError("Unknown/empty manifest")
    names=[row["path"] for row in rows]
    if len(names)!=len(set(names)) or len(names)!=len({n.casefold() for n in names}):raise ValueError("Duplicate paths")
    if set(names)&{"MANIFEST.json","SHA256SUMS"}:raise ValueError("Manifest self-reference")
    for row in rows:
        data=read(row["path"])
        if len(data)!=row["bytes"] or sha(data)!=row["sha256"]:raise ValueError("Payload mismatch: "+row["path"])
    sums={}
    for line in read("SHA256SUMS").decode("utf-8").splitlines():
        digest,name=line.split("  ",1)
        if name in sums or not valid(name) or digest!=sha(read(name)):raise ValueError("Checksum mismatch: "+name)
        sums[name]=digest
    expected=set(names)|{"MANIFEST.json","SHA256SUMS"}
    actual=set()
    for path in ROOT.rglob("*"):
        if path.is_symlink() or getattr(path,"is_junction",lambda:False)():raise ValueError("Linked path: "+str(path))
        if path.is_file():
            if not regular(path):raise ValueError("Nonregular path")
            actual.add(path.relative_to(ROOT).as_posix())
        elif not path.is_dir():raise ValueError("Nonregular packet entry: "+str(path))
    if actual!=expected or set(sums)!=expected-{"SHA256SUMS"}:raise ValueError("Packet/checksum membership mismatch")
    print(json.dumps({"status":"PASS","payloadFiles":len(rows),"checksumEntries":len(sums),"totalFiles":len(expected),"scope":"Complete local byte/membership verification only; no engine code or authored work executed."}))
except (OSError,ValueError,KeyError,TypeError) as error:
    print("Package verification failed: "+str(error),file=sys.stderr)
    raise SystemExit(1)
