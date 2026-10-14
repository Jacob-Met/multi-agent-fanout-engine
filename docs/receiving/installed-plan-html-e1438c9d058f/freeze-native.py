"""Metadata-only admission. Does not run the installed comparator."""
import importlib.util
import json
import os
from pathlib import Path
import pwd
import shutil
import socket
import sys

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("receiving_common", ROOT / "receiving_common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
identity, tree, state, pin, save = common.identity, common.tree, common.state, common.pin, common.save
OLD = Path("/home/jacob/hamon-e1438c9d058f-installed-plan-compare")
if str(ROOT) != "/home/jacob/hamon-e1438c9d058f-installed-plan-html":
    raise RuntimeError("wrong receiving namespace")
if socket.gethostname() != "hamon-thinkpad" or os.getuid() != 1000 or pwd.getpwuid(1000).pw_name != "jacob":
    raise RuntimeError("wrong device/account")
pins = {
    "activation-config.json": (538124, "f17861eae4cd0051ffbd8fbe4f8ae4afd73417b5b6f7cc0c898b604fb18245c5"),
    "activation-receiving/receipt.json": (1140107, "90b409f05da0e6c0833c017ffd5e027fd1514e40660f7afbdfdeb2b3ce22eb45"),
    "activation-postexit.json": (3882, "d1476a177284fffee71ae27e547226f76c15c8ab9553eda56c3909a16fc818ad"),
}
prior = {}
for name, (size, digest) in pins.items():
    data = (OLD / name).read_bytes()
    if len(data) != size or pin(data)["sha256"] != digest:
        raise RuntimeError("accepted prior receipt differs: " + name)
    prior[name] = json.loads(data)
old = prior["activation-config.json"]
receipt = prior["activation-receiving/receipt.json"]
post = prior["activation-postexit.json"]
if receipt["status"] != "PASS" or receipt["passed"] != 16 or receipt["failed"] or post["status"] != "PASS" or not post["preservation"]:
    raise RuntimeError("prior acceptance differs")
if state(old) != receipt["before"] or receipt["before"] != receipt["after"]:
    raise RuntimeError("prior installation/source/input membership drift")
if identity(old["alias"]) != post["actual_alias"] or post["actual_alias"] != receipt["actual_alias"]:
    raise RuntimeError("installed alias differs")
if post["actual_alias"]["target"] != old["version"] + "/hamon-fanout-read" or shutil.which("hamon-fanout-read") != old["alias"]:
    raise RuntimeError("installed PATH route differs")
if tree(OLD / "installed") != post["installed_files"] or tree(OLD / "activation-receiving") != post["output_files"]:
    raise RuntimeError("prior actual outputs drift")
if identity(OLD / "activation-process.json") != post["process"]:
    raise RuntimeError("prior process receipt drift")
manifest = json.loads((ROOT / "source-inputs.json").read_bytes())
inputs = dict(old["inputs"])
for name, wanted in manifest["files"].items():
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError("unsafe source manifest path")
    actual = identity(ROOT / path)
    if any(actual[key] != wanted[key] for key in ("bytes", "sha256", "git")):
        raise RuntimeError("source input drift: " + name)
    inputs[str(ROOT / path)] = actual
for name in ("source-inputs.json", "route-admission.json", "stage-receipt.json"):
    inputs[str(ROOT / name)] = identity(ROOT / name)
for name in (*pins, "activation-process.json", "installation-receipt.json"):
    inputs[str(OLD / name)] = identity(OLD / name)
oracle = json.loads((ROOT / "root-frozen-expectations.json").read_bytes())
expected = (ROOT / "expected-comparison.json").read_bytes()
if pin(expected)["sha256"] != "107eb14f39b9a3e7175a538a1db5394f6f09d39e9a51bd225ee071f44fb0d9bb" or len(expected) != 3250 or json.loads(expected) != oracle["report"]:
    raise RuntimeError("frozen independent oracle differs")
if expected != (OLD / "installed/comparison.json").read_bytes():
    raise RuntimeError("accepted native comparison differs")
protected = dict(old["protected"])
protected[old["alias"]] = post["actual_alias"]
if str(Path(sys.executable).resolve()) not in protected:
    raise RuntimeError("receiver interpreter not in accepted runtime")
roots = dict(old["roots"])
for path in (OLD / "installed", OLD / "activation-receiving", ROOT / "source"):
    roots[str(path)] = tree(path)
absent = [str(ROOT / name) for name in ("native-config.json", "native-receiving", "result", "native-postexit.json")]
if any(os.path.lexists(p) for p in absent + old["must_remain_absent"]):
    raise RuntimeError("new destination occupied or prior recovery artifact present")
if os.statvfs(ROOT).f_bavail * os.statvfs(ROOT).f_frsize < 64 * 1024 * 1024:
    raise RuntimeError("insufficient receiving capacity")
config = {"schema": "hamon.installed-plan-html.native-config/1", "old_root": str(OLD),
          "alias": old["alias"], "runtime_commit": old["source_commit"], "published_wrapper_merge": old["merge_commit"],
          "output": str(ROOT / "native-receiving"), "result": str(ROOT / "result/comparison.html"),
          "command": ["/usr/bin/env", "hamon-fanout-read", "compare", "--before", str(OLD / "inputs/before.json"),
                      "--after", str(OLD / "inputs/after.json"), "--format", "html", "--output", str(ROOT / "result/comparison.html")],
          "absent": absent[1:], "must_remain_absent": old["must_remain_absent"],
          "protected": protected, "inputs": inputs, "roots": roots, "frozen": oracle}
save(ROOT / "native-config.json", config)
print(json.dumps({"status": "FROZEN_UNRUN", "config": pin((ROOT / "native-config.json").read_bytes()),
                  "protected": len(protected), "inputs": len(inputs), "roots": {p: len(v) for p, v in roots.items()}}))
