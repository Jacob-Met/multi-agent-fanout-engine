"""One installed HTML export and read-only receipt; never installs or dispatches."""
import base64
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("receiving_common", ROOT / "receiving_common.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
identity, tree, state, pin, save = common.identity, common.tree, common.state, common.pin, common.save


class Document(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "root", "attrs": {}, "children": []}
        self.stack = [self.root]
        self.nodes = []

    def handle_starttag(self, tag, attrs):
        node = {"tag": tag, "attrs": dict(attrs), "children": []}
        self.stack[-1]["children"].append(node)
        self.nodes.append(node)
        if tag not in {"meta", "link", "img", "br", "hr", "input", "source", "wbr", "area", "base", "col", "embed", "param", "track"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        if len(self.stack) < 2 or self.stack[-1]["tag"] != tag:
            raise RuntimeError("unbalanced HTML: " + tag)
        self.stack.pop()

    def handle_data(self, text):
        self.stack[-1]["children"].append(text)

    def select(self, tag=None, identity=None):
        return [n for n in self.nodes if (tag is None or n["tag"] == tag) and
                (identity is None or n["attrs"].get("id") == identity)]


def text(node):
    return node if isinstance(node, str) else "".join(text(c) for c in node["children"])


cfg_path = ROOT / "native-config.json"
cfg_raw = cfg_path.read_bytes()
cfg = json.loads(cfg_raw)
expected_state = {k: cfg[k] for k in ("protected", "inputs", "roots")}
before = state(cfg)
if before != expected_state:
    raise RuntimeError("native admission drift")
if identity(__file__) != cfg["inputs"][str(Path(__file__).resolve())]:
    raise RuntimeError("controller identity differs")
if identity(Path(sys.executable).resolve()) != cfg["protected"][str(Path(sys.executable).resolve())]:
    raise RuntimeError("interpreter differs")
if socket.gethostname() != "hamon-thinkpad" or os.getuid() != 1000 or shutil.which("hamon-fanout-read") != cfg["alias"]:
    raise RuntimeError("machine/account/PATH differs")
command = ["/usr/bin/env", "hamon-fanout-read", "compare", "--before", cfg["old_root"] + "/inputs/before.json",
           "--after", cfg["old_root"] + "/inputs/after.json", "--format", "html", "--output", str(ROOT / "result/comparison.html")]
if command != cfg["command"] or any(os.path.lexists(p) for p in cfg["absent"] + cfg["must_remain_absent"]):
    raise RuntimeError("command or fresh destination differs")
out = Path(cfg["output"])
out.mkdir()
(ROOT / "result").mkdir()
env = dict(os.environ)
report = {"schema": "hamon.installed-plan-html.native-receipt/1", "status": "RUNNING", "pid": os.getpid(),
          "config": pin(cfg_raw), "before": before, "checks": [], "known_pids": [os.getpid()]}


def check(name, value):
    report["checks"].append({"name": name, "passed": bool(value)})
    if not value:
        raise RuntimeError("receiving check failed: " + name)


try:
    process = {"argv": command, "timeout_seconds": 15, "post_kill_wait_seconds": 3,
               "timed_out": False, "post_kill_wait_timeout": False}
    started = time.monotonic()
    with (out / "stdout.bin").open("xb") as stdout, (out / "stderr.bin").open("xb") as stderr:
        child = subprocess.Popen(command, cwd=ROOT, env=None, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        process["pid"] = child.pid
        report["known_pids"].append(child.pid)
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process["timed_out"] = True
            try:
                child.kill()
            except OSError as exc:
                process["kill_error"] = {"type": type(exc).__name__, "message": str(exc)}
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process["post_kill_wait_timeout"] = True
        process.update(returncode=child.poll(), reaped=child.returncode is not None,
                       elapsed=time.monotonic() - started, known_pid_present=Path("/proc/" + str(child.pid)).exists())
    stdout = (out / "stdout.bin").read_bytes()
    stderr = (out / "stderr.bin").read_bytes()
    process.update(stdout=pin(stdout), stderr=pin(stderr))
    report["process"] = process
    save(out / "process.json", process)
    check("one ordinary installed command reaped0 without timeout", process["returncode"] == 0 and process["reaped"] and
          not any(process[k] for k in ("known_pid_present", "timed_out", "post_kill_wait_timeout")))
    check("file export raw streams empty", stdout == stderr == b"")
    html = Path(cfg["result"]).read_bytes()
    report["html"] = identity(cfg["result"])
    check("bounded UTF8 HTML with final newline", 0 < len(html) <= 32 * 1024 * 1024 and html.endswith(b"\n"))
    doc = Document()
    doc.feed(html.decode("utf-8"))
    doc.close()
    check("balanced complete HTML", len(doc.stack) == 1 and len(doc.select("html")) == len(doc.select("body")) == len(doc.select("main")) == 1)
    frozen = cfg["frozen"]
    one = lambda tag=None, identity=None: doc.select(tag, identity)[0] if len(doc.select(tag, identity)) == 1 else None
    check("title and heading exact", text(one("title")) == frozen["title"] and text(one("h1")) == frozen["heading"])
    check("all summary flags and added/removed lists exact", all(text(one(identity=k)) == v for k, v in frozen["summary"].items()))
    check("complete native plans exact", all(json.loads(text(one(identity=side + "-plan-json"))) == plan for side, plan in frozen["full_plans"].items()))
    check("all five complete key rows exact", all(json.loads(text(one(identity=f"key-{i}-{suffix}"))) == row[key]
          for i, row in enumerate(frozen["keys"]) for suffix, key in (("part", "part_id"), ("before", "before"), ("after", "after"), ("changed", "changed"))))
    tables = doc.select("tbody")
    rows = [[text(c) for c in tr["children"] if isinstance(c, dict)] for tr in tables[0]["children"] if isinstance(tr, dict)]
    check("three full native identity rows exact", len(tables) == 2 and [[r[0], json.loads(r[1]), json.loads(r[2])] for r in rows] == frozen["identity_rows"])
    check("empty changed-fields message exact", any(text(p) == frozen["no_changes"] for p in doc.select("p")))
    links = doc.select("a")
    check("one fixed-name JSON data download", len(links) == 1 and links[0]["attrs"].get("download") == "plan-comparison.json" and
          links[0]["attrs"].get("href", "").startswith("data:application/json;base64,"))
    embedded = base64.b64decode(links[0]["attrs"]["href"].split(",", 1)[1], validate=True)
    report["embedded_json"] = pin(embedded)
    check("embedded JSON exact accepted3250 bytes and full oracle", embedded == (ROOT / "expected-comparison.json").read_bytes() and
          len(embedded) == 3250 and json.loads(embedded) == frozen["report"])
    check("no executable or external resource markup", not any(n["tag"] in {"script", "iframe", "object", "embed", "form", "link", "img", "base"} or
          any(k.startswith("on") or k in {"src", "srcset", "action", "formaction"} for k in n["attrs"]) for n in doc.nodes))
    check("restrictive offline content policy", any(n["attrs"].get("http-equiv") == "Content-Security-Policy" and n["attrs"].get("content") ==
          "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'" for n in doc.select("meta")))
except BaseException as exc:
    report["error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    # Retain launch/collection failures as observations, including any streams
    # opened before Popen failed. Never start a replacement process.
    if "process" in locals() and not (out / "process.json").exists():
        process["receiving_error"] = report["error"]
        process["elapsed"] = time.monotonic() - started
        for stream in ("stdout", "stderr"):
            path = out / (stream + ".bin")
            process[stream] = pin(path.read_bytes()) if path.is_file() else {"absent": True}
        report["process"] = process
        save(out / "process.json", process)
finally:
    try:
        report["after"] = state(cfg)
        check("all prior runtime/alias/source/inputs and membership preserved", report["after"] == before)
        check("config and caller environment preserved", cfg_path.read_bytes() == cfg_raw and dict(os.environ) == env)
        check("no old recovery artifact", not any(os.path.lexists(p) for p in cfg["must_remain_absent"]))
        report["known_processes"] = {str(p): Path("/proc/" + str(p)).exists() for p in report["known_pids"] if p != os.getpid()}
        check("observed native process absent", not any(report["known_processes"].values()))
        report["result_files"] = tree(ROOT / "result")
        report["output_files"] = tree(out)
    except BaseException as exc:
        report["finalization_error"] = {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}
    report["passed"] = sum(c["passed"] for c in report["checks"])
    report["failed"] = len(report["checks"]) - report["passed"]
    report["status"] = "PASS" if not report.get("error") and not report.get("finalization_error") and not report["failed"] else "FAIL"
    report["failure_disposition"] = "Preserve actual outputs and process records. No cleanup, installation, retry, dispatch or rollback."
    save(out / "receipt.json", report)
    print(json.dumps({"status": report["status"], "passed": report["passed"], "failed": report["failed"],
                      "known_pids": report["known_pids"], "receipt": pin((out / "receipt.json").read_bytes()), "html": report.get("html")}))
raise SystemExit(0 if report["status"] == "PASS" else 1)
