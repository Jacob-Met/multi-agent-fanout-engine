#!/usr/bin/env python3
"""Install one new user-owned, versioned Fanout reader command; no live ledger default."""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import shutil
import socket
import stat
import subprocess
import sys
import zipfile

COMMIT = "639038bb09a14b54109efd2df2e699a22484a815"
TREE = "fbb6e1317c2b733539f36335d89fdc6ad39be351"
ROOT = Path("/home/jacob/fanout-readers-20261013-c4c3dc26dd94")
VERSION = Path("/home/jacob/.local/share/hamon-tools/hamon-fanout-read-639038bb09a1")
ALIAS = Path("/home/jacob/.local/bin/hamon-fanout-read")
PYTHON = Path("/usr/bin/python3.14")
PYTHON_SHA = "52e0a13e60a981d8c4b6478be2ba5176f69da07948a056bf49cf6f077e30cb41"
ARCHIVE = ROOT / "Fanout-Current-Reader-Wheel-Build-c4c3dc26dd94.zip"
ARCHIVE_SHA = "f6bacba529169097b44804a3fe1ba63c4e778d569ac585b9e389ba1cf12ab65b"
ARCHIVE_GIT = "f5e3d7f8862e764ae70ce3ba1e3380df4d23a1df"
WHEEL = "multi_agent_fanout_engine-0.1.0-py3-none-any.whl"
WHEEL_SHA = "29b74d701c5f088357bc19c3c7cf95b3f8226edddba379a82669b4c46a25d5ad"
MANIFEST_SHA = "7d6fe0702001eb03227656dd50c29970caf162cc821df3ab7fd1ed53385cc3f8"
PIP_WHEEL = Path("/usr/share/python-wheels/pip-25.1.1-py3-none-any.whl")
PIP_SHA = "2b5bcfb34fdd1ec0c864cb9029e69831cf95a02570382ca56b62bef08c1cbf1d"
EXAMPLE_GIT = "0e0bc5d8ea3790ce4bb5028cbe3b1725fcedb21a"
DIRECTORIES = {
    "/home/jacob": (66306, 262146),
    "/home/jacob/.local": (66306, 262152),
    "/home/jacob/.local/bin": (66306, 412413),
    "/home/jacob/.local/share": (66306, 262153),
    "/home/jacob/.local/share/hamon-tools": (66306, 4594380),
}
HELP = """hamon-fanout-read: saved Fanout ledger readers
Usage:
  hamon-fanout-read projects --database FILE [--output NEW.json]
  hamon-fanout-read inspect  --database FILE --project ID [--output NEW.json]
  hamon-fanout-read history  --database FILE --project ID [--part ID] [--output NEW.json]
  hamon-fanout-read review   --database FILE --project ID --output NEW.html

FILE must be an explicitly selected existing local ledger. No default ledger is used.
Readers preserve recorded uncertainty; they do not dispatch, retry or reconcile work.
Exports require a new output path. SQLite may maintain read-side WAL bookkeeping.
Use a subcommand's --help for its exact options. Source: 639038bb09a1.
"""
WRAPPER = ("#!/bin/sh\n"
    "case \"${1-}\" in\n"
    "  -h|--help) cat <<'FANOUT_HELP'\n" + HELP + "FANOUT_HELP\n    exit 0 ;;\n"
    "  projects|inspect|history|review) route=$1; shift ;;\n"
    "  *) printf '%s\\n' 'Use: hamon-fanout-read --help (projects, inspect, history, review only)' >&2; exit 2 ;;\n"
    "esac\n"
    "exec '" + str(VERSION / "venv/bin/python") + "' -I -B -m \"fanout_engine.$route\" \"$@\"\n").encode()

def require(ok, message):
    if not ok:
        raise RuntimeError(message)

def pins(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "git": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}

def identity(path):
    s = path.lstat()
    row = {"dev": s.st_dev, "ino": s.st_ino, "mode": s.st_mode,
           "uid": s.st_uid, "gid": s.st_gid, "mtime_ns": s.st_mtime_ns, "size": s.st_size}
    if stat.S_ISREG(s.st_mode):
        row.update(pins(path.read_bytes()))
    elif stat.S_ISLNK(s.st_mode):
        row["target"] = os.readlink(path)
    else:
        require(stat.S_ISDIR(s.st_mode), "unexpected file kind: " + str(path))
    return row

def ordinary(path, owned=True):
    row = identity(path)
    require(stat.S_ISREG(row["mode"]), "not an ordinary file: " + str(path))
    if owned:
        require(row["uid"] == 1000, "not owned by jacob: " + str(path))
    return row

def write_new(path, data, mode=0o600):
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(mode)

def record(path, value):
    write_new(path, (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode())

def preflight(require_absent=True):
    require(os.getuid() == os.geteuid() == 1000 and os.getgid() == 1000, "account ID changed")
    require(pwd.getpwuid(os.getuid()).pw_name == "jacob" and socket.gethostname() == "hamon-thinkpad", "host/account changed")
    require(Path(sys.executable).resolve() == PYTHON and sys.version_info[:3] == (3,14,4), "interpreter changed")
    require(ordinary(PYTHON, False)["sha256"] == PYTHON_SHA, "interpreter bytes changed")
    for name, pair in DIRECTORIES.items():
        s = Path(name).lstat()
        require(stat.S_ISDIR(s.st_mode) and s.st_uid == s.st_gid == 1000 and (s.st_dev, s.st_ino) == pair, "directory identity changed: " + name)
    s = ROOT.lstat()
    require(stat.S_ISDIR(s.st_mode) and s.st_uid == 1000 and not (s.st_mode & 0o077), "workdir must be private and ordinary")
    ordinary(Path(__file__))
    if require_absent:
        require(not os.path.lexists(ALIAS), "alias is occupied")
        for entry in os.environ.get("PATH", "").split(os.pathsep):
            candidate = Path(entry or ".") / ALIAS.name
            require(not os.path.lexists(candidate), "command collision: " + str(candidate))
    return {"host": socket.gethostname(), "uid": os.getuid(), "gid": os.getgid(),
            "python": str(PYTHON), "python_sha256": PYTHON_SHA, "path": os.environ.get("PATH", ""),
            "source_commit": COMMIT, "source_tree": TREE}

def read_archive():
    archive_identity = ordinary(ARCHIVE)
    require(archive_identity["bytes"] == 114764 and archive_identity["sha256"] == ARCHIVE_SHA
            and archive_identity["git"] == ARCHIVE_GIT, "build archive changed")
    with zipfile.ZipFile(ARCHIVE) as z:
        entries = z.infolist()
        names = [i.filename for i in entries]
        require(len(entries) == len(set(names)) == 37, "archive membership changed")
        for info in entries:
            path = PurePosixPath(info.filename)
            require(not path.is_absolute() and ".." not in path.parts and "\\" not in info.filename
                    and not info.is_dir() and stat.S_IFMT(info.external_attr >> 16) in (0, stat.S_IFREG),
                    "unsafe archive member")
        data = {name: z.read(name) for name in names}
    require(pins(data["BUILD-MANIFEST.json"])["sha256"] == MANIFEST_SHA, "build manifest changed")
    manifest = json.loads(data["BUILD-MANIFEST.json"])
    require(set(data) == set(manifest["files"]) | {"BUILD-MANIFEST.json"}, "manifest membership changed")
    for name, expected in manifest["files"].items():
        require(pins(data[name]) == expected, "archive byte pin changed: " + name)
    build = json.loads(data["wheel/source-build.json"])
    require(build["wheel"]["modules"] == 19 and build["wheel"]["record_entries"] == 23
            and build["wheel"]["sha256"] == WHEEL_SHA and build["build"]["returncode"] == 0, "build result not accepted")
    require(pins(data["wheel/" + WHEEL])["sha256"] == WHEEL_SHA, "wheel changed")
    require(pins(data["source/examples/create_retained_ledger.py"])["git"] == EXAMPLE_GIT, "fixture source changed")
    terminal = json.loads(data["build-job/receipt.json"])
    require(terminal["child_returncode"] == terminal["receiver_exit_code"] == 0
            and terminal["child_reaped"] is True and terminal["sources_unchanged"] is True
            and terminal["inspection_errors"] == [], "cloud build terminal gate failed")
    return data, build, archive_identity

def clean_environment():
    env = {k:v for k,v in os.environ.items() if not k.startswith(("PIP_", "PYTHON"))}
    env.update(PIP_CONFIG_FILE=os.devnull, PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
    return env

def child(directory, label, argv, expected, timeout=15, env=None):
    out = directory / (label + ".stdout.bin")
    err = directory / (label + ".stderr.bin")
    row = {"argv": [str(a) for a in argv], "expected_exit": expected}
    with out.open("xb") as stdout, err.open("xb") as stderr:
        p = subprocess.Popen(row["argv"], cwd=directory, env=env, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        row["pid"] = p.pid
        row["timed_out"] = False
        try:
            code = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            row["timed_out"] = True
            p.kill()
            code = p.wait()
    row.update(returncode=code, child_reaped=p.poll() is not None,
               stdout=pins(out.read_bytes()), stderr=pins(err.read_bytes()))
    record(directory / (label + ".json"), row)
    require(not row["timed_out"] and row["child_reaped"] and code == expected, "unexpected child outcome: " + label)
    return out.read_bytes(), err.read_bytes(), row

def installed_files(build):
    site = VERSION / "venv/lib/python3.14/site-packages"
    expected = {name:pin for name,pin in build["source"]["files"].items() if name.startswith("fanout_engine/")}
    require(len(expected) == 19, "runtime closure changed")
    actual = {str(p.relative_to(site)): p for p in (site / "fanout_engine").rglob("*.py")}
    require(set(actual) == set(expected), "installed module set changed")
    rows = {}
    for name, path in actual.items():
        row = ordinary(path)
        pin = expected[name]
        require(row["bytes"] == pin["bytes"] and row["sha256"] == pin["sha256"] and row["git"] == pin["git_blob"], "installed module differs: " + name)
        rows[str(path)] = row
    for path in (VERSION / "hamon-fanout-read", VERSION / "examples/create_retained_ledger.py",
                 VERSION / "distribution" / WHEEL, VERSION / "venv/pyvenv.cfg",
                 site / "multi_agent_fanout_engine-0.1.0.dist-info/METADATA",
                 site / "multi_agent_fanout_engine-0.1.0.dist-info/RECORD"):
        rows[str(path)] = ordinary(path)
    require((VERSION / "hamon-fanout-read").read_bytes() == WRAPPER, "wrapper changed")
    require((VERSION / "venv/bin/python").resolve() == PYTHON, "venv interpreter target changed")
    return rows

def stage():
    context = preflight()
    data, build, archive_before = read_archive()
    require(not os.path.lexists(VERSION), "version exists; do not repeat stage")
    require(ordinary(PIP_WHEEL, False)["sha256"] == PIP_SHA, "bundled pip changed")
    course = ROOT / "stage"
    course.mkdir(mode=0o700)
    VERSION.mkdir(mode=0o700)
    (VERSION / "distribution").mkdir(mode=0o700)
    (VERSION / "examples").mkdir(mode=0o700)
    write_new(VERSION / "distribution" / WHEEL, data["wheel/" + WHEEL])
    write_new(VERSION / "examples/create_retained_ledger.py", data["source/examples/create_retained_ledger.py"])
    write_new(VERSION / "source-build.json", data["wheel/source-build.json"])
    env = clean_environment()
    child(course, "venv", [PYTHON, "-I", "-B", "-m", "venv", VERSION / "venv"], 0, 90, env)
    py = VERSION / "venv/bin/python"
    child(course, "install-wheel", [py, "-I", "-B", "-m", "pip", "install", "--no-index", "--no-deps",
          "--no-cache-dir", "--no-compile", "--disable-pip-version-check", VERSION / "distribution" / WHEEL], 0, 60, env)
    write_new(VERSION / "hamon-fanout-read", WRAPPER, 0o755)
    before = installed_files(build)
    database = course / "authored-sample.sqlite"
    child(course, "fixture", [py, "-I", "-B", VERSION / "examples/create_retained_ledger.py", database], 0)
    fixture_before = ordinary(database)
    command = VERSION / "hamon-fanout-read"
    observations = []
    def run(label, args, code=0):
        out, err, row = child(course, label, [command, *args], code)
        observations.append({"label":label, **row})
        return out, err
    out, err = run("help", ["--help"])
    require(out == HELP.encode() and not err, "help mismatch")
    out, err = run("reject-dispatch", ["dispatch"], 2)
    require(not out and b"only" in err, "nonreader was not refused")
    out, err = run("explicit-database-required", ["projects"], 2)
    require(not out and b"--database" in err, "missing database did not refuse")
    out, err = run("projects", ["projects", "--database", str(database)])
    catalog = json.loads(out)
    require(not err and catalog["project_count"] == 1 and catalog["projects"][0]["project_id"] == "sample"
            and catalog["projects"][0]["part_count"] == 7, "catalog mismatch")
    inspection, err = run("inspect", ["inspect", "--database", str(database), "--project", "sample"])
    report = json.loads(inspection)
    require(not err and report["project_id"] == "sample" and len(report["parts"]) == 7
            and report["state_counts"] == {"queued":2,"dispatching":1,"running":1,"completed":1,"outcome_unknown":1,"failed":1}
            and report["queued_ready_ids"] == ["notes"] and report["blocked_queued_ids"] == ["publish"], "inspection semantics changed")
    history, err = run("history", ["history", "--database", str(database), "--project", "sample"])
    timeline = json.loads(history)
    require(not err and timeline["project_id"] == "sample" and len(timeline["events"]) > 7
            and any(r["part_id"] == "rejected" and r["event"] == "reconciled" and r["detail"]["verdict"] == "failed"
                    for r in timeline["events"]), "history mismatch")
    html = course / "sample-review.html"
    out, err = run("review", ["review", "--database", str(database), "--project", "sample", "--output", str(html)])
    page = html.read_bytes()
    match = re.search(rb'href="data:application/json;base64,([A-Za-z0-9+/=]+)"', page)
    require(not out and not err and match and base64.b64decode(match[1], validate=True) == inspection, "HTML exact JSON differs")
    html_before = ordinary(html)
    out, err = run("occupied-review", ["review", "--database", str(database), "--project", "sample", "--output", str(html)], 1)
    require(not out and b"output already exists" in err and ordinary(html) == html_before, "occupied output changed")
    missing = course / "missing.sqlite"
    out, err = run("missing-database", ["projects", "--database", str(missing)], 2)
    require(not out and not os.path.lexists(missing) and b"cannot read ledger" in err, "missing database changed")
    require(ordinary(database) == fixture_before, "fixture database changed")
    require(installed_files(build) == before and ordinary(ARCHIVE) == archive_before, "runtime/build custody changed")
    require(not os.path.lexists(ALIAS), "alias appeared during staging")
    receipt = {**context, "phase":"staged", "observations":observations, "runtime":before,
               "fixture":fixture_before, "database":str(database), "review":html_before,
               "archive":archive_before, "all_checks_passed":True, "live_ledger_used":False}
    record(ROOT / "staged-receipt.json", receipt)
    print(json.dumps({"phase":"staged","checks":len(observations),"version":str(VERSION),"alias_absent":True}))

def activate():
    context = preflight()
    data, build, archive_before = read_archive()
    stage_receipt = json.loads((ROOT / "staged-receipt.json").read_bytes())
    require(stage_receipt["all_checks_passed"] is True and len(stage_receipt["observations"]) == 9
            and all(r["returncode"] == r["expected_exit"] and not r["timed_out"] and r["child_reaped"] for r in stage_receipt["observations"]), "stage not accepted")
    require(installed_files(build) == stage_receipt["runtime"], "staged runtime changed")
    database = Path(stage_receipt["database"])
    require(database == ROOT / "stage/authored-sample.sqlite" and ordinary(database) == stage_receipt["fixture"], "staged fixture changed")
    course = ROOT / "activation"
    course.mkdir(mode=0o700)
    alias_identity = None
    try:
        os.symlink(str(VERSION / "hamon-fanout-read"), ALIAS)
        alias_identity = identity(ALIAS)
        require(shutil.which(ALIAS.name) == str(ALIAS), "inherited PATH does not resolve new alias")
        out, err, help_row = child(course, "inherited-help", ["/usr/bin/env", ALIAS.name, "--help"], 0)
        require(out == HELP.encode() and not err, "inherited help mismatch")
        out, err, history_row = child(course, "inherited-history", ["/usr/bin/env", ALIAS.name, "history",
                          "--database", database, "--project", "sample"], 0)
        require(not err and out == (ROOT / "stage/history.stdout.bin").read_bytes(), "inherited history differs")
        require(identity(ALIAS) == alias_identity and installed_files(build) == stage_receipt["runtime"]
                and ordinary(database) == stage_receipt["fixture"] and ordinary(ARCHIVE) == archive_before, "post-install custody changed")
        receipt = {**context, "phase":"installed", "alias":str(ALIAS), "alias_identity":alias_identity,
                   "runtime":stage_receipt["runtime"], "fixture":stage_receipt["fixture"],
                   "observations":[help_row, history_row], "all_checks_passed":True}
        record(ROOT / "installation-receipt.json", receipt)
        print(json.dumps({"phase":"installed","alias":str(ALIAS),"observations":2,"alias_identity":alias_identity}))
    except BaseException as exc:
        disposition = "new alias not captured; inspect before any action"
        if alias_identity is not None:
            if os.path.lexists(ALIAS) and identity(ALIAS) == alias_identity:
                ALIAS.unlink()
                disposition = "removed exact newly-created alias; version preserved"
            else:
                disposition = "alias identity drift; left untouched"
        record(ROOT / "activation-failure.json", {"error":repr(exc),"alias_identity":alias_identity,"disposition":disposition})
        raise

def withdraw():
    preflight(False)
    receipt = json.loads((ROOT / "installation-receipt.json").read_bytes())
    require(receipt["alias"] == str(ALIAS) and identity(ALIAS) == receipt["alias_identity"], "alias changed; withdrawal refused")
    require(os.readlink(ALIAS) == str(VERSION / "hamon-fanout-read"), "target changed")
    ALIAS.unlink()
    record(ROOT / "withdrawal-receipt.json", {"removed_alias":str(ALIAS),"prior_alias_identity":receipt["alias_identity"],
                                             "version_preserved":str(VERSION)})
    print("Removed the exact installed alias; version and receiving evidence remain.")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("stage","activate","withdraw"))
    args = parser.parse_args()
    {"stage":stage,"activate":activate,"withdraw":withdraw}[args.phase]()

if __name__ == "__main__":
    main()
