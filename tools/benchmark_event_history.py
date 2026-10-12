"""Receive project history from the same native disk records before/after indexing."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time


def digest_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def logical_digest(database):
    digest = hashlib.sha256()
    connection = sqlite3.connect(Path(database).as_uri() + "?mode=ro", uri=True)
    try:
        for table, order in (("projects", "project_id"), ("parts", "project_id,part_id"), ("events", "seq")):
            digest.update((table + "\n").encode())
            for row in connection.execute(f"SELECT * FROM {table} ORDER BY {order}"):
                digest.update((json.dumps(row, ensure_ascii=True, allow_nan=False) + "\n").encode())
    finally:
        connection.close()
    return digest.hexdigest()


def deny_network(event, args):
    if event.startswith("socket."):
        raise RuntimeError("this retained-ledger benchmark does not use the network")


def child(args):
    sys.addaudithook(deny_network)
    sys.path.insert(0, str(Path(args.source).resolve()))
    start = time.perf_counter()
    from fanout_engine import Ledger, Part, Plan
    from fanout_engine.history import inspect_history
    from fanout_engine.plan import canonical_json

    if args.mode == "fixture":
        with Ledger() as ledger:
            def record(project, finding):
                plan = Plan(project, (Part("one", "Retain authored work."),
                                      Part("waiting", "Wait for verified work.", ("one",))))
                ledger.record_plan(plan)
                ledger.mark_dispatching(project, "one", "fixture-worker",
                                        {"model": "fixture-model", "effort": "low"})
                ledger.mark_running(project, "one", "accepted-" + project)
                ledger.mark_outcome_unknown(project, "one", {
                    "source": "authored fixture", "locator": plan.idempotency_key("one"),
                    "finding": finding,
                })

            record("target", "Unresolved authored receipt; no external work was submitted.")
            for index in range(args.neighbors):
                record("neighbor-" + str(index), "x" * args.finding_bytes)
            expected = canonical_json(inspect_history(ledger, "target")).encode()
            destination = sqlite3.connect(args.database)
            try:
                ledger._db.backup(destination)
            finally:
                destination.close()
        return {"fixture_create_s": time.perf_counter() - start,
                "projects": args.neighbors + 1, "events": 4 * (args.neighbors + 1),
                "database_bytes": Path(args.database).stat().st_size,
                "database_sha256": digest_file(args.database),
                "logical_rows_sha256": logical_digest(args.database),
                "history_sha256": hashlib.sha256(expected).hexdigest()}

    if args.mode == "migrate":
        # The ordinary writable constructor performs the one-time index build.
        start = time.perf_counter()
        with Ledger(args.database):
            pass
        return {"writable_open_s": time.perf_counter() - start,
                "database_bytes": Path(args.database).stat().st_size,
                "database_sha256": digest_file(args.database),
                "logical_rows_sha256": logical_digest(args.database)}

    before_sha = digest_file(args.database)
    start = time.perf_counter()
    with Ledger.open_readonly(args.database) as ledger:
        opened = time.perf_counter()
        hashes = []
        for _ in range(args.reads):
            encoded = canonical_json(inspect_history(ledger, "target")).encode()
            hashes.append(hashlib.sha256(encoded).hexdigest())
        queries_done = time.perf_counter()
    finished = time.perf_counter()
    assert len(set(hashes)) == 1
    assert digest_file(args.database) == before_sha

    # Count SQLite work separately, outside the timed receiving section.
    steps = 0

    def count_step():
        nonlocal steps
        steps += 1
        return 0

    with Ledger.open_readonly(args.database) as ledger:
        ledger._db.set_progress_handler(count_step, 1)
        try:
            diagnostic = canonical_json(inspect_history(ledger, "target")).encode()
        finally:
            ledger._db.set_progress_handler(None, 0)
    assert hashlib.sha256(diagnostic).hexdigest() == hashes[0]
    assert digest_file(args.database) == before_sha
    return {"open_s": opened - start, "read_and_serialize_s": queries_done - opened,
            "complete_read_workflow_s": finished - start, "reads": args.reads,
            "history_sha256": hashes[0], "history_bytes": len(encoded),
            "database_sha256": before_sha, "database_unchanged": True,
            "diagnostic_sqlite_vm_steps": steps}


CLI_BOOTSTRAP = """import sys,runpy
def deny_network(event,args):
    if event.startswith('socket.'):
        raise RuntimeError('retained history CLI cannot use the network')
sys.addaudithook(deny_network)
sys.path.insert(0,sys.argv.pop(1))
runpy.run_module('fanout_engine.history',run_name='__main__')
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before")
    parser.add_argument("--after")
    parser.add_argument("--neighbors", type=int, default=1500)
    parser.add_argument("--finding-bytes", type=int, default=4096)
    parser.add_argument("--reads", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--mode", choices=("fixture", "migrate", "receive"))
    parser.add_argument("--source")
    parser.add_argument("--database")
    args = parser.parse_args()
    if min(args.neighbors, args.finding_bytes, args.reads, args.repeats) < 1:
        parser.error("neighbor, finding, read and repeat counts must be positive")
    if args.mode:
        if not args.source or not args.database:
            parser.error("a child mode requires source and database")
        print(json.dumps(child(args), sort_keys=True))
        return
    if not args.before or not args.after:
        parser.error("before and after source paths are required")
    sources = {label: str(Path(getattr(args, label)).resolve()) for label in ("before", "after")}
    pins = {label: {path.name: digest_file(path) for path in (Path(source) / "fanout_engine").glob("*.py")}
            for label, source in sources.items()}

    def run(mode, source, database):
        command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()),
                   "--mode", mode, "--source", source, "--database", str(database),
                   "--neighbors", str(args.neighbors), "--finding-bytes", str(args.finding_bytes),
                   "--reads", str(args.reads)]
        output = subprocess.run(command, capture_output=True, check=True, timeout=120)
        return json.loads(output.stdout)

    result = {"python": sys.version, "sqlite": sqlite3.sqlite_version, "platform": platform.platform(),
              "source_sha256": pins, "neighbors": args.neighbors,
              "finding_bytes": args.finding_bytes, "reads_per_process": args.reads,
              "repeats": args.repeats, "method": "Same native logical records; copied disk files; one explicit writable upgrade; alternating fresh read-only processes and actual history CLI commands; no network."}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        databases = {label: root / (label + ".sqlite3") for label in sources}
        fixture = run("fixture", sources["before"], databases["before"])
        shutil.copyfile(databases["before"], databases["after"])
        migration = run("migrate", sources["after"], databases["after"])
        assert fixture["logical_rows_sha256"] == migration["logical_rows_sha256"]
        samples = {label: [] for label in sources}
        clis = []
        for repetition in range(args.repeats):
            order = ("before", "after") if repetition % 2 == 0 else ("after", "before")
            for label in order:
                sample = run("receive", sources[label], databases[label])
                assert sample["history_sha256"] == fixture["history_sha256"]
                samples[label].append(sample)
                command = [sys.executable, "-I", "-B", "-c", CLI_BOOTSTRAP, sources[label],
                           "--database", str(databases[label]), "--project", "target"]
                started = time.perf_counter()
                output = subprocess.run(command, cwd=root, capture_output=True, check=True, timeout=30)
                elapsed = time.perf_counter() - started
                assert output.stderr == b"" and output.stdout.endswith(b"\n")
                assert hashlib.sha256(output.stdout[:-1]).hexdigest() == fixture["history_sha256"]
                assert digest_file(databases[label]) == sample["database_sha256"]
                clis.append({"source": label, "returncode": output.returncode,
                             "wall_s": elapsed, "stdout_bytes": len(output.stdout),
                             "stderr_bytes": len(output.stderr),
                             "stdout_sha256": hashlib.sha256(output.stdout).hexdigest()})
        assert digest_file(databases["before"]) == fixture["database_sha256"]
        assert digest_file(databases["after"]) == migration["database_sha256"]
        result.update({"fixture": fixture, "writable_upgrade": migration,
                       "samples": samples, "actual_history_clis": clis,
                       "medians": {label: {
                           "read_and_serialize_s": statistics.median(s["read_and_serialize_s"] for s in rows),
                           "complete_read_workflow_s": statistics.median(s["complete_read_workflow_s"] for s in rows),
                           "actual_cli_wall_s": statistics.median(s["wall_s"] for s in clis if s["source"] == label),
                       } for label, rows in samples.items()}})
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
