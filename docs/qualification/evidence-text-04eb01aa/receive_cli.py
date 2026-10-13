#!/usr/bin/env python3
"""Receive the PR67 runtime in owned fixtures; no network, adapter, or provider."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

SOURCE_COMMIT = "9b8265a56727e085b99a691e925cc4cfcafb57a7"
PINS = [
  {
    "path": "fanout_engine/__init__.py",
    "blob": "d0ca3bb491865798e334dfe137906b00f802a3b8"
  },
  {
    "path": "fanout_engine/compare.py",
    "blob": "fb478246d94d6dfab6671910a641f86eab60d78c"
  },
  {
    "path": "fanout_engine/dispatch.py",
    "blob": "973c1882d83c9ba32d64d95456cbd695a230f05c"
  },
  {
    "path": "fanout_engine/history.py",
    "blob": "80bf355f9a1c791bcc53737f5b3db441fe8aea3c"
  },
  {
    "path": "fanout_engine/inspect.py",
    "blob": "827b5760a0a95bd7960b084708225ebd478e3ff3"
  },
  {
    "path": "fanout_engine/inspection.py",
    "blob": "2944a58dae77ce7b5bf91f0637d4c5e7686c7e34"
  },
  {
    "path": "fanout_engine/ledger.py",
    "blob": "7007a3cedccd83410c9ebc592c393000a6013c0b"
  },
  {
    "path": "fanout_engine/plan.py",
    "blob": "69a633cacd6f32e8bbc6d0d580db3b2fcb14ec82"
  },
  {
    "path": "fanout_engine/preview.py",
    "blob": "3af98db006853a19f60506322f7e450ce3685cfc"
  },
  {
    "path": "fanout_engine/projects.py",
    "blob": "6589dba3740f51e42cafd6b484912818cccac211"
  },
  {
    "path": "fanout_engine/routing.py",
    "blob": "436a9f014caf69960fce67de28c062a431805b99"
  }
]

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def snapshot(source, captured=None):
    result = {}
    for entry in PINS:
        path = source / entry["path"]
        require(path.is_file() and not path.is_symlink(), "missing or linked source: " + entry["path"])
        data = path.read_bytes()
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        require(blob == entry["blob"], "source blob mismatch: " + entry["path"])
        result[entry["path"]] = {"git_blob": blob, "sha256": hashlib.sha256(data).hexdigest()}
        if captured is not None:
            captured[entry["path"]] = data
    return result

def run(source, output):
    source = source.resolve(strict=True)
    output = output.absolute()
    require(source.is_dir(), "source must be a directory")
    require(source != output.resolve() and source not in output.resolve().parents,
            "receiving output must be outside source")
    captured = {}
    before = snapshot(source, captured)
    output.mkdir(mode=0o700)  # Exclusive; never reuse an existing receiving directory.
    require(not any(k == "fanout_engine" or k.startswith("fanout_engine.") for k in sys.modules),
            "start a fresh Python process without an already loaded fanout package")
    runtime = output / "runtime"
    for name, data in captured.items():
        target = runtime / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(data)
    require(snapshot(runtime) == before, "staged runtime mismatch")
    sys.path.insert(0, str(runtime))
    sys.dont_write_bytecode = True
    from fanout_engine.ledger import Ledger, LedgerError
    from fanout_engine.plan import Part, Plan

    project = "evidence-receiving"
    plan = Plan(project, (Part("work", "Owned local receiving fixture."),
                         Part("dependent", "Wait for work.", ("work",))))
    database = output / "receiving.sqlite3"
    controls = []
    class Blank(str):
        def strip(self, *args):
            return "override says nonempty"
    class Surrogate(str):
        def encode(self, *args, **kwargs):
            return b"override says UTF8"
    class Valid(str):
        def strip(self, *args):
            return ""

    finding = "  verified café 東京  "
    accepted = {"source": "owned local fixture", "locator": "fixture://receiving/work",
                "finding": Valid(finding), "extra": "retained supplementary detail"}
    with Ledger(str(database)) as ledger:
        ledger.record_plan(plan)
        ledger.mark_dispatching(project, "work", "local-receiver", {"model": "fixture", "effort": "low"})
        ledger.mark_running(project, "work", "owned-task")
        for name, value in (("blank_literal", Blank(" \t ")),
                            ("surrogate_literal", Surrogate("\ud800"))):
            rows = ledger.part(project, "work")
            events = ledger.events(project, "work")
            db_before = database.read_bytes()
            statements = []
            ledger._db.set_trace_callback(statements.append)
            error = None
            try:
                ledger.mark_failed(project, "work", dict(accepted, finding=value))
            except LedgerError as exc:
                error = str(exc)
            finally:
                ledger._db.set_trace_callback(None)
            require(error is not None, name + " was not refused")
            require(not statements, name + " reached SQL")
            require(ledger.part(project, "work") == rows and ledger.events(project, "work") == events,
                    name + " changed retained state")
            require(database.read_bytes() == db_before, name + " changed database bytes")
            controls.append({"control": name, "result": "LedgerError", "diagnostic": error,
                             "sql_statements": len(statements), "database_bytes_unchanged": True})
        ledger.mark_failed(project, "work", accepted)
        require(ledger.part(project, "work")["evidence"] == accepted, "literal evidence changed")

    db_bytes = database.read_bytes()
    db_mtime = database.stat().st_mtime_ns
    commands = []
    reports = {}
    launcher = ("import runpy,sys;sys.path.insert(0,sys.argv.pop(1));"
                "runpy.run_module(sys.argv.pop(1),run_name='__main__')")
    for name in ("projects", "inspect", "history"):
        arguments = ["--database", str(database)]
        if name != "projects":
            arguments += ["--project", project]
        command = [sys.executable, "-I", "-B", "-c", launcher, str(runtime),
                   "fanout_engine." + name] + arguments
        result = subprocess.run(command, capture_output=True, timeout=20)
        (output / (name + ".stdout")).write_bytes(result.stdout)
        (output / (name + ".stderr")).write_bytes(result.stderr)
        commands.append({"module": name, "arguments": arguments, "returncode": result.returncode,
                         "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                         "stderr_sha256": hashlib.sha256(result.stderr).hexdigest()})
        require(result.returncode == 0 and not result.stderr, name + " CLI failed")
        reports[name] = json.loads(result.stdout.decode("utf-8"))
        require(database.read_bytes() == db_bytes and database.stat().st_mtime_ns == db_mtime,
                name + " changed database bytes or modification time")
    require(reports["projects"]["projects"] ==
            [{"project_id": project, "plan_digest": plan.digest, "part_count": 2}],
            "projects identity mismatch")
    inspection = reports["inspect"]
    require(inspection["plan_digest"] == plan.digest, "inspection identity mismatch")
    require([(p["id"], p["state"]) for p in inspection["parts"]] ==
            [("work", "failed"), ("dependent", "queued")], "inspection state mismatch")
    require(inspection["queued_ready_ids"] == [] and inspection["blocked_queued_ids"] == ["dependent"],
            "failed prerequisite no longer blocks dependent")
    require(inspection["parts"][0]["evidence"] == accepted, "inspect evidence mismatch")
    history = reports["history"]
    require(history["plan_digest"] == plan.digest, "history identity mismatch")
    require(history["events"][-1]["event"] == "failed" and
            history["events"][-1]["detail"] == accepted, "history evidence mismatch")
    require(snapshot(source) == before, "received source changed")
    require(snapshot(runtime) == before, "staged runtime changed")
    require(sorted(p.name for p in output.iterdir()) ==
            ["history.stderr", "history.stdout", "inspect.stderr", "inspect.stdout",
             "projects.stderr", "projects.stdout", "receiving.sqlite3", "runtime"],
            "unexpected receiving file or SQLite sidecar")
    receipt = {"schema": "fanout.evidence-cli-receiving/1", "source_commit": SOURCE_COMMIT,
               "python": sys.version, "sqlite": sqlite3.sqlite_version,
               "source_files": before, "controls": controls, "commands": commands,
               "plan_digest": plan.digest, "finding": finding,
               "database_sha256": hashlib.sha256(db_bytes).hexdigest(),
               "source_unchanged": True, "runtime_copy_unchanged": True,
               "runtime_copy": "runtime", "database_read_windows_unchanged": True,
               "consumer_contract": "Literal evidence retained in state and history; dependent stays queued",
               "result": "PASS"}
    text = json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    payload = text.encode("utf-8")
    (output / "receipt.json").write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    digest = run(args.source, args.out)
    print("PASS: receipt SHA-256 " + digest)

if __name__ == "__main__":
    main()
