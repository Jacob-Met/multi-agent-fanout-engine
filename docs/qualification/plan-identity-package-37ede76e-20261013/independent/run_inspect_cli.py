"""Invoke the maintained inspect CLI from an isolated, explicitly pinned import path."""
import hashlib
import json
from pathlib import Path
import runpy
import sys

repo = Path(sys.argv.pop(1)).resolve()
provenance = Path(sys.argv.pop(1)).resolve()
sys.path.insert(0, str(repo))
try:
    runpy.run_module("fanout_engine.inspect", run_name="__main__")
finally:
    modules = {}
    for name, module in sorted(sys.modules.items()):
        if name == "fanout_engine" or name.startswith("fanout_engine."):
            path = Path(module.__file__).resolve()
            relative = path.relative_to(repo).as_posix()
            data = path.read_bytes()
            modules[name] = {
                "path": str(path), "relative_path": relative,
                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(),
            }
    target = repo / "fanout_engine" / "inspect.py"
    data = target.read_bytes()
    record = {
        "target": "fanout_engine.inspect",
        "target_path": str(target),
        "target_git_blob": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(),
        "argv": sys.argv,
        "isolated": sys.flags.isolated,
        "dont_write_bytecode": sys.dont_write_bytecode,
        "imported_modules": modules,
    }
    with provenance.open("x", encoding="utf-8") as output:
        output.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
