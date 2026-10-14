"""Actual retained-ledger/CLI courses for advisory queued-route projection."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import Ledger, Part, Plan, Route, EffortRouter
from fanout_engine.queued_routes import queued_route_report

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = {"source": "authored-fixture", "locator": "fixture://local", "finding": "observed"}
CATALOG = {"fixture-a": ["low", "high"], "fixture-b": ["high"]}


def start(ledger, project, part):
    ledger.mark_dispatching(project, part, "local-fixture", {"model": "fixture-a", "effort": "low"})
    ledger.mark_running(project, part, "task-" + part)


def seed(path):
    plan = Plan("project-3795", (
        Part("beta", "private instruction", ("done",), ("z", "a", "z")),
        Part("done", "completed"),
        Part("unknown", "uncertain"),
        Part("blocked", "wait", ("unknown",)),
        Part("alpha", "independent"),
        Part("running", "in flight"),
        Part("failed", "terminal failure"),
        Part("block-failed", "wait", ("failed",)),
        Part("dispatching", "in flight"),
    ))
    with Ledger(str(path)) as ledger:
        ledger.record_plan(plan)
        start(ledger, plan.project_id, "done")
        ledger.mark_completed(plan.project_id, "done", "fixture://artifact", EVIDENCE)
        ledger.mark_dispatching(plan.project_id, "unknown", "local-fixture", {"model": "fixture-a", "effort": "low"})
        ledger.mark_outcome_unknown(plan.project_id, "unknown", EVIDENCE)
        start(ledger, plan.project_id, "running")
        start(ledger, plan.project_id, "failed")
        ledger.mark_failed(plan.project_id, "failed", EVIDENCE)
        ledger.mark_dispatching(plan.project_id, "dispatching", "local-fixture", {"model": "fixture-a", "effort": "low"})
    return plan


class QueuedRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="queued-routes-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.database = self.root / "retained #1 ?.sqlite3"
        self.plan = seed(self.database)
        self.routing = self.root / "routes.json"
        self.document = {
            "catalog": CATALOG,
            "pool": [{"model": "fixture-a", "effort": "low"}],
            "explicit_routes": {"beta": {"model": "fixture-b", "effort": "high"}},
            "step_up": {"model": "fixture-a", "effort": "high"},
        }
        self.save_routes()

    def save_routes(self):
        self.routing.write_text(json.dumps(self.document) + "\n", encoding="utf-8")

    def invoke(self, *extra, database=None, routes=None, project=None, stdout=subprocess.PIPE):
        return subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.queued_routes",
             "--database", str(database or self.database),
             "--project", project or self.plan.project_id,
             "--routes", str(routes or self.routing), *extra],
            cwd=ROOT, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            stdout=stdout, stderr=subprocess.PIPE, timeout=10,
        )

    def test_actual_cli_routes_from_retained_state_and_preserves_inputs(self):
        before = {p: (p.read_bytes(), p.stat().st_mtime_ns, p.stat().st_mode) for p in (self.database, self.routing)}
        result = self.invoke()
        self.assertEqual((result.returncode, result.stderr), (0, b""))
        report = json.loads(result.stdout)
        self.assertEqual(report["queued_ready_ids"], ["beta", "alpha"])
        self.assertEqual(report["blocked_queued_ids"], ["blocked", "block-failed"])
        self.assertEqual(report["state_counts"], {"queued": 4, "completed": 1, "outcome_unknown": 1, "running": 1, "failed": 1, "dispatching": 1})
        self.assertEqual([p["id"] for p in report["parts"]], [p.id for p in self.plan.parts])
        self.assertEqual(report["parts"][3]["unmet_dependencies"], [{"id": "unknown", "state": "outcome_unknown"}])
        self.assertEqual(report["parts"][7]["unmet_dependencies"], [{"id": "failed", "state": "failed"}])
        self.assertEqual(report["routes"], [
            {"part_id": "beta", "route": {"model": "fixture-b", "effort": "high"}, "route_source": "explicit", "idempotency_key": self.plan.idempotency_key("beta")},
            {"part_id": "alpha", "route": {"model": "fixture-a", "effort": "low"}, "route_source": "pool", "idempotency_key": self.plan.idempotency_key("alpha")},
        ])
        self.assertEqual(report["plan_digest"], self.plan.digest)
        self.assertEqual(report["routing_input_sha256"], hashlib.sha256(self.routing.read_bytes()).hexdigest())
        self.assertEqual(report["configured_step_up"], {"model": "fixture-a", "effort": "high"})
        self.assertNotIn(b"private instruction", result.stdout)
        self.assertNotIn(b"fixture://artifact", result.stdout)
        for p, expected in before.items():
            self.assertEqual((p.read_bytes(), p.stat().st_mtime_ns, p.stat().st_mode), expected)

    def test_single_snapshot_leaves_caller_transaction_owned(self):
        with Ledger(str(self.database)) as ledger:
            ledger._db.execute("BEGIN")
            ledger._db.execute("UPDATE parts SET updated_at=updated_at+1 WHERE part_id='alpha'")
            traces = []
            ledger._db.set_trace_callback(traces.append)
            report = queued_route_report(ledger, self.plan.project_id, EffortRouter(CATALOG, pool=(Route("fixture-a", "low"),)))
            self.assertTrue(ledger._db.in_transaction)
            self.assertEqual(report["queued_ready_ids"], ["beta", "alpha"])
            self.assertEqual(len(traces), 1)
            self.assertTrue(traces[0].lstrip().startswith("SELECT"))
            ledger._db.set_trace_callback(None)
            ledger._db.rollback()

    def test_every_override_validates_including_empty_ready_snapshot(self):
        for part, route in [("blocked", {"model": "fixture-a", "effort": "ultra"}),
                            ("absent", {"model": "fixture-a", "effort": "low"})]:
            with self.subTest(part=part):
                self.document["explicit_routes"] = {part: route}
                self.save_routes()
                result = self.invoke()
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, b"")
        with Ledger(str(self.database)) as ledger:
            for part in ("beta", "alpha"):
                start(ledger, self.plan.project_id, part)
                ledger.mark_completed(self.plan.project_id, part, "fixture://done")
        self.document["explicit_routes"] = {}
        self.save_routes()
        empty = self.invoke()
        self.assertEqual(empty.returncode, 0)
        self.assertEqual(json.loads(empty.stdout)["routes"], [])
        self.document["explicit_routes"] = {"unknown": {"model": "fixture-a", "effort": "ultra"}}
        self.save_routes()
        result = self.invoke()
        self.assertEqual((result.returncode, result.stdout), (2, b""))

    def test_usage_admission_precedes_file_access(self):
        missing = self.root / "missing" / "ledger.sqlite3"
        for extra in [("--project", "other"), ("--database", str(missing)),
                      ("--routes", str(missing)), ("--output", str(missing), "--output", str(missing)), ("--dat", str(missing))]:
            with self.subTest(extra=extra):
                result = self.invoke(*extra, database=missing, routes=missing)
                self.assertEqual((result.returncode, result.stdout), (2, b""))
                self.assertNotIn(b"cannot preview", result.stderr)
        help_result = subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.queued_routes", "--help"],
            cwd=ROOT, capture_output=True, timeout=10,
        )
        self.assertEqual((help_result.returncode, help_result.stderr), (0, b""))
        self.assertFalse(missing.parent.exists())

    def test_read_errors_distinguish_unknown_project_and_leave_no_output(self):
        missing = self.root / "missing.sqlite3"
        result = self.invoke(database=missing)
        self.assertEqual((result.returncode, result.stdout), (2, b""))
        self.assertFalse(missing.exists())
        unknown = self.invoke(project="not-recorded")
        self.assertEqual((unknown.returncode, unknown.stdout), (3, b""))
        self.assertIn(b"project_not_found", unknown.stderr)
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute("UPDATE parts SET evidence_json='[] broken' WHERE part_id='failed'")
        bad = self.invoke()
        self.assertEqual((bad.returncode, bad.stdout), (2, b""))
        self.assertIn(b"invalid_record", bad.stderr)

    def test_routing_regular_bounded_strict_input_then_healthy_recovery(self):
        for content in [b'{"catalog":{},"catalog":{}}', b'{"pool":[NaN]}', b"\xff", b" " * (256 * 1024 + 1), b"[" * 2000]:
            with self.subTest(prefix=content[:30]):
                self.routing.write_bytes(content)
                result = self.invoke()
                self.assertEqual((result.returncode, result.stdout), (2, b""))
                self.assertNotIn(b"Traceback", result.stderr)
        result = self.invoke(routes=self.root)
        self.assertEqual((result.returncode, result.stdout), (2, b""))
        if hasattr(os, "mkfifo"):
            fifo = self.root / "routes.pipe"
            os.mkfifo(fifo)
            result = self.invoke(routes=fifo)
            self.assertEqual((result.returncode, result.stdout), (2, b""))
        self.save_routes()
        self.assertEqual(self.invoke().returncode, 0)

    def test_retained_part_limit_does_not_change_database(self):
        database = self.root / "large.sqlite3"
        plan = Plan("large", tuple(Part(f"part-{i}", "fixture") for i in range(257)))
        with Ledger(str(database)) as ledger:
            ledger.record_plan(plan)
        before = database.read_bytes()
        result = self.invoke(database=database, project="large")
        self.assertEqual((result.returncode, result.stdout), (2, b""))
        self.assertIn(b"256 parts", result.stderr)
        self.assertEqual(database.read_bytes(), before)

    @unittest.skipUnless(os.name == "posix", "requires POSIX child file descriptor control")
    def test_closed_stdout_has_normal_output_error(self):
        result = subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.queued_routes",
             "--database", str(self.database), "--project", self.plan.project_id,
             "--routes", str(self.routing)],
            cwd=ROOT, capture_output=True, timeout=10,
            preexec_fn=lambda: os.close(1),
        )
        self.assertEqual((result.returncode, result.stdout), (1, b""))
        self.assertIn(b"cannot write report: standard output is unavailable", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    @unittest.skipUnless(Path("/dev/full").exists(), "requires a real failing stdout device")
    def test_real_output_error_is_distinct(self):
        with open("/dev/full", "wb", buffering=0) as sink:
            result = self.invoke(stdout=sink)
        self.assertEqual(result.returncode, 1)
        self.assertIn(b"cannot write report", result.stderr)


    @staticmethod
    def _output_entry(path):
        if not os.path.lexists(path):
            return None
        metadata = path.lstat()
        details = (metadata.st_dev, metadata.st_ino, metadata.st_mode,
                   metadata.st_size, metadata.st_mtime_ns)
        if path.is_symlink():
            return details, os.readlink(path)
        if path.is_dir():
            return details, None
        return details, path.read_bytes()

    def _retained_output_inputs(self):
        paths = [self.database, self.routing]
        paths.extend(Path(str(self.database) + suffix)
                     for suffix in ("-wal", "-shm", "-journal"))
        return {str(path): self._output_entry(path) for path in paths}

    def test_new_output_matches_complete_stdout_and_preserves_inputs(self):
        before = self._retained_output_inputs()
        ordinary = self.invoke()
        self.assertEqual((ordinary.returncode, ordinary.stderr), (0, b""))
        destination = self.root / "queued report.json"
        result = self.invoke("--output", str(destination))
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        self.assertEqual(destination.read_bytes(), ordinary.stdout)
        self.assertTrue(ordinary.stdout.endswith(b"\n"))
        self.assertEqual(json.loads(destination.read_bytes())["queued_ready_ids"], ["beta", "alpha"])
        self.assertEqual(self._retained_output_inputs(), before)
        self.assertEqual(list(self.root.glob(".fanout-preview-*")), [])

    @unittest.skipUnless(os.name == "posix", "requires POSIX child file descriptor control")
    def test_new_output_succeeds_with_actual_stdout_closed(self):
        before = self._retained_output_inputs()
        ordinary = self.invoke()
        self.assertEqual((ordinary.returncode, ordinary.stderr), (0, b""))
        destination = self.root / "closed-stdout.json"
        result = subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.queued_routes",
             "--database", str(self.database), "--project", self.plan.project_id,
             "--routes", str(self.routing), "--output", str(destination)],
            cwd=ROOT, capture_output=True, timeout=10,
            preexec_fn=lambda: os.close(1),
        )
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, b"", b""))
        self.assertEqual(destination.read_bytes(), ordinary.stdout)
        self.assertEqual(self._retained_output_inputs(), before)
        self.assertEqual(list(self.root.glob(".fanout-preview-*")), [])

    def test_output_refusals_preserve_existing_and_sqlite_paths(self):
        sentinel = self.root / "occupied.json"
        sentinel.write_bytes(b"keep existing output\x00\xff")
        directory = self.root / "output-directory"
        directory.mkdir()
        destinations = [sentinel, directory, self.database, self.routing]
        destinations.extend(Path(str(self.database) + suffix)
                            for suffix in ("-wal", "-shm", "-journal"))
        if os.name == "posix":
            dangling = self.root / "dangling.json"
            dangling.symlink_to(self.root / "absent-target")
            hardlink = self.root / "hardlinked-database"
            os.link(self.database, hardlink)
            linked = self.root / "linked-database"
            linked.symlink_to(self.database)
            destinations.extend([dangling, Path(str(hardlink) + "-wal"),
                                 Path(str(linked) + "-shm")])
        destinations.append(self.root / "missing-parent" / "report.json")
        retained = self._retained_output_inputs()
        for destination in destinations:
            with self.subTest(destination=destination.name):
                before = self._output_entry(destination)
                result = self.invoke("--output", str(destination))
                self.assertEqual((result.returncode, result.stdout), (1, b""))
                self.assertIn(b"cannot write report", result.stderr)
                self.assertIn(str(destination).encode(), result.stderr)
                self.assertNotIn(b"Traceback", result.stderr)
                self.assertEqual(self._output_entry(destination), before)
                self.assertEqual(self._retained_output_inputs(), retained)
                self.assertEqual(list(self.root.glob(".fanout-preview-*")), [])
        self.assertFalse((self.root / "missing-parent").exists())
        self.assertFalse((self.root / "absent-target").exists())

    def test_output_validation_errors_keep_input_status_and_no_publication(self):
        destination = self.root / "unknown.json"
        unknown = self.invoke("--output", str(destination), project="not-recorded")
        self.assertEqual((unknown.returncode, unknown.stdout), (3, b""))
        self.assertIn(b"project_not_found", unknown.stderr)
        self.assertFalse(destination.exists())
        destination.write_bytes(b"retained occupied output")
        before = self._output_entry(destination)
        unknown = self.invoke("--output", str(destination), project="not-recorded")
        self.assertEqual((unknown.returncode, unknown.stdout), (3, b""))
        self.assertEqual(self._output_entry(destination), before)
        self.routing.write_bytes(b"{invalid routing")
        refused = self.root / "invalid-input.json"
        invalid = self.invoke("--output", str(refused))
        self.assertEqual((invalid.returncode, invalid.stdout), (2, b""))
        self.assertIn(b"cannot preview retained routes", invalid.stderr)
        self.assertFalse(refused.exists())
        self.save_routes()
        missing = self.invoke("--output", str(refused), database=self.root / "absent.sqlite3")
        self.assertEqual((missing.returncode, missing.stdout), (2, b""))
        self.assertFalse(refused.exists())
        self.assertEqual(list(self.root.glob(".fanout-preview-*")), [])


if __name__ == "__main__":
    unittest.main()
