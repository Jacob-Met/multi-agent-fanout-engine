"""Read-only postexit collection of the sole installed HTML export."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("receiving_common", ROOT / "receiving_common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
identity, tree, state, pin, save = common.identity, common.tree, common.state, common.pin, common.save
config_raw = (ROOT / "native-config.json").read_bytes()
config = json.loads(config_raw)
raw = (ROOT / "native-receiving/receipt.json").read_bytes()
receipt = json.loads(raw)
if receipt["status"] != "PASS" or receipt["failed"] or receipt["config"] != pin(config_raw):
    raise RuntimeError("native receipt not accepted or config changed")
if state(config) != receipt["before"] or receipt["before"] != receipt["after"]:
    raise RuntimeError("preserved state drift")
if tree(ROOT / "result") != receipt["result_files"]:
    raise RuntimeError("actual HTML changed")
outputs = tree(ROOT / "native-receiving")
if {k: v for k, v in outputs.items() if k != "receipt.json"} != receipt["output_files"]:
    raise RuntimeError("raw observations changed")
if any(Path("/proc/" + str(pid)).exists() for pid in receipt["known_pids"]):
    raise RuntimeError("owned process remains")
post = {"schema": "hamon.installed-plan-html.native-postexit/1", "status": "PASS",
        "receipt": pin(raw), "config": pin(config_raw), "pids": {str(p): None for p in receipt["known_pids"]},
        "result_files": receipt["result_files"], "output_files": outputs, "preservation": True,
        "scope": "Read-only after native controller completion; no product replay."}
save(ROOT / "native-postexit.json", post)
print(json.dumps({"status": "PASS", "postexit": pin((ROOT / "native-postexit.json").read_bytes()), "pids": post["pids"]}))
