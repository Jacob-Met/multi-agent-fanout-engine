"""Focused real-consumer checks for creating a new queued ledger."""
from __future__ import annotations

from contextlib import redirect_stderr
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from fanout_engine import create_ledger
from fanout_engine.preview import PreviewError, _publish_new_file


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


class CreateLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fanout-create-tests-")
        self.root = Path(self.temporary.name)
        self.plan_file = self.root / "authored café.json"
        self.database = self.root / "queued café.sqlite3"
        self.document = {
            "project": "authored-local",
            "parts": [
                {"id": "draft", "instruction": "Write café notes.\nRetain this line.", "tags": ["z", "a", "z"]},
                {"id": "review", "instruction": "Read the notes.", "depends_on": ["draft"], "tags": ["review"]},
            ],
        }
        self.native = {
            "project": "authored-local",
            "parts": [
                {"id": "draft", "instruction": "Write café notes.\nRetain this line.", "depends_on": [], "tags": ["a", "z"]},
                {"id": "review", "instruction": "Read the notes.", "depends_on": ["draft"], "tags": ["review"]},
            ],
        }
        self.input_bytes = (json.dumps(self.document, ensure_ascii=False, indent=2) + "\n").encode()
        self.plan_file.write_bytes(self.input_bytes)
        self.source_root = Path(__file__).resolve().parents[1]

    def tearDown(self):
        self.temporary.cleanup()

    def command(self, plan=None, database=None, module="fanout_engine.create_ledger", extra=(), **kwargs):
        flags = ["-O"] if sys.flags.optimize else []
        args = [sys.executable, *flags, "-B", "-m", module, *extra]
        if module == "fanout_engine.create_ledger":
            args += ["--plan", str(plan or self.plan_file), "--database", str(database or self.database)]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.source_root)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(args, cwd=self.root, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=15, **kwargs)

    def read_database(self, path=None):
        target = path or self.database
        connection = sqlite3.connect(target.absolute().as_uri() + "?mode=ro", uri=True)
        try:
            connection.row_factory = sqlite3.Row
            return {
                "projects": [dict(r) for r in connection.execute("SELECT * FROM projects ORDER BY project_id")],
                "parts": [dict(r) for r in connection.execute("SELECT * FROM parts ORDER BY part_id")],
                "events": [dict(r) for r in connection.execute("SELECT * FROM events ORDER BY seq")],
            }
        finally:
            connection.close()

    def check_new_database(self, result, path=None, receipt=True):
        target = path or self.database
        self.assertEqual(result.returncode, 0 if receipt else 1, result.stderr)
        data = target.read_bytes()
        rows = self.read_database(target)
        plan_digest = digest(canonical(self.native))
        self.assertEqual(rows["projects"], [{
            "project_id": "authored-local", "plan_digest": plan_digest,
            "plan_json": canonical(self.native).decode(),
        }])
        self.assertEqual(len(rows["parts"]), 2)
        for row, part in zip(rows["parts"], self.native["parts"]):
            self.assertEqual(row["project_id"], "authored-local")
            self.assertEqual(row["part_id"], part["id"])
            self.assertEqual(row["payload_json"], canonical(part).decode())
            self.assertEqual(row["payload_digest"], plan_digest)
            key = "fanout-" + digest(("authored-local\0" + plan_digest + "\0" + part["id"]).encode())
            self.assertEqual(row["idempotency_key"], key)
            self.assertEqual(row["state"], "queued")
            for field in ("worker_id", "task_id", "route_json", "artifact_ref", "evidence_json"):
                self.assertIsNone(row[field])
            self.assertTrue(math.isfinite(row["updated_at"]))
        self.assertEqual(len(rows["events"]), 1)
        event = rows["events"][0]
        self.assertEqual(
            {k: event[k] for k in ("seq", "project_id", "part_id", "event", "detail_json")},
            {"seq": 1, "project_id": "authored-local", "part_id": None, "event": "plan_recorded",
             "detail_json": canonical({"part_count": 2, "plan_digest": plan_digest}).decode()},
        )
        self.assertTrue(math.isfinite(event["at"]))
        if receipt:
            expected = {
                "schema_version": 1, "database": str(target), "project_id": "authored-local",
                "plan_digest": plan_digest, "part_count": 2,
                "input_sha256": digest(self.input_bytes), "database_sha256": digest(data),
            }
            self.assertEqual(result.stdout, canonical(expected) + b"\n")
            self.assertEqual(result.stderr, b"")
        self.assertEqual(self.plan_file.read_bytes(), self.input_bytes)
        return data

    def test_creation_and_existing_readonly_consumers(self):
        result = self.command()
        original = self.check_new_database(result)
        report = self.command(module="fanout_engine.inspect",
                              extra=("--database", str(self.database), "--project", "authored-local"))
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertEqual(json.loads(report.stdout)["state_counts"]["queued"], 2)
        exported = self.command(module="fanout_engine.export_plan",
                                extra=("--database", str(self.database), "--project", "authored-local"))
        self.assertEqual(exported.returncode, 0, exported.stderr)
        self.assertEqual(exported.stdout, canonical(self.native) + b"\n")
        self.assertEqual(self.database.read_bytes(), original)

    def test_existing_destination_and_input_alias_are_unchanged(self):
        for destination in (self.database, self.plan_file):
            with self.subTest(destination=destination.name):
                if destination != self.plan_file:
                    destination.write_bytes(b"existing destination bytes")
                before = destination.read_bytes()
                stamp = destination.stat().st_mtime_ns
                result = self.command(database=destination)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"publication did not complete normally", result.stderr)
                self.assertEqual(destination.read_bytes(), before)
                self.assertEqual(destination.stat().st_mtime_ns, stamp)

    def test_repeat_does_not_replace_a_recorded_database(self):
        original = self.check_new_database(self.command())
        before = self.database.stat()
        result = self.command()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, b"")
        self.assertEqual(self.database.read_bytes(), original)
        self.assertEqual(self.database.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(self.database.stat().st_ino, before.st_ino)

    def test_reserved_destination_basenames_refuse(self):
        for suffix in ("-wal", "-shm", "-journal", "-WAL", "-ShM", "-JOURNAL"):
            with self.subTest(suffix=suffix):
                destination = self.root / ("reserved.sqlite3" + suffix)
                result = self.command(database=destination)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertFalse(os.path.lexists(destination))
                self.assertIn(b"filename must not end", result.stderr)

    def test_existing_sqlite_sidecars_are_preserved(self):
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                sidecar = Path(str(self.database) + suffix)
                sidecar.write_bytes(b"preserved sidecar")
                before = sidecar.stat()
                result = self.command()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertFalse(self.database.exists())
                self.assertEqual(sidecar.read_bytes(), b"preserved sidecar")
                self.assertEqual(sidecar.stat().st_mtime_ns, before.st_mtime_ns)
                self.assertEqual(sidecar.stat().st_ino, before.st_ino)
                sidecar.unlink()

    def test_sidecar_directory_and_dangling_link_refuse(self):
        directory = Path(str(self.database) + "-journal")
        directory.mkdir()
        (directory / "sentinel").write_bytes(b"directory child")
        result = self.command()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(self.database.exists())
        self.assertEqual((directory / "sentinel").read_bytes(), b"directory child")
        (directory / "sentinel").unlink()
        directory.rmdir()
        link = Path(str(self.database) + "-wal")
        try:
            link.symlink_to(self.root / "absent-target")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on this consumer")
        result = self.command()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertFalse(self.database.exists())
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(link), str(self.root / "absent-target"))

    def test_bad_input_precedes_destination_admission(self):
        bad = [
            b'{"project":"x","project":"y","parts":[]}',
            b"\xff",
            b'{"project":"x","parts":[{"id":"one","instruction":"x","depends_on":["missing"]}]}',
            b'{"project":"x","parts":[{"id":"one","instruction":"x","depends_on":["one"]}]}',
            b'{"project":"x","parts":[{"id":"one","instruction":"x","tags":[NaN]}]}',
        ]
        self.database.write_bytes(b"occupied")
        for value in bad:
            with self.subTest(value=value):
                self.plan_file.write_bytes(value)
                result = self.command()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertIn(b"preparation failed before publication", result.stderr)
                self.assertEqual(self.database.read_bytes(), b"occupied")
                self.assertEqual(self.plan_file.read_bytes(), value)

    def test_input_limits_are_inherited(self):
        oversized = b" " * (1024 * 1024 + 1)
        many = canonical({"project": "many", "parts": [
            {"id": f"p{i}", "instruction": "keep"} for i in range(257)
        ]})
        for value in (oversized, many):
            with self.subTest(size=len(value)):
                self.plan_file.write_bytes(value)
                result = self.command()
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(result.stdout, b"")
                self.assertFalse(self.database.exists())
                self.assertEqual(self.plan_file.read_bytes(), value)

    def test_missing_input_and_missing_output_parent(self):
        result = self.command(plan=self.root / "no-input.json")
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.database.exists())
        destination = self.root / "no-parent" / "new.sqlite3"
        result = self.command(database=destination)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(destination.parent.exists())

    def test_private_preparation_failure_publishes_nothing(self):
        error = io.StringIO()
        with patch.object(create_ledger, "Ledger", side_effect=sqlite3.OperationalError("controlled preparation failure")):
            with redirect_stderr(error):
                result = create_ledger.main(["--plan", str(self.plan_file), "--database", str(self.database)])
        self.assertEqual(result, 2)
        self.assertIn("preparation failed before publication", error.getvalue())
        self.assertFalse(self.database.exists())
        self.assertEqual(self.plan_file.read_bytes(), self.input_bytes)

    def test_late_publication_error_does_not_claim_absence(self):
        def publish_then_report_failure(destination, content):
            _publish_new_file(destination, content)
            raise PreviewError("published but controlled staging cleanup failure")
        error = io.StringIO()
        with patch.object(create_ledger, "_publish_new_file", side_effect=publish_then_report_failure):
            with redirect_stderr(error):
                result = create_ledger.main(["--plan", str(self.plan_file), "--database", str(self.database)])
        self.assertEqual(result, 1)
        self.assertTrue(self.database.is_file())
        self.assertIn("inspect the destination before retrying", error.getvalue())
        self.assertEqual(len(self.read_database()["events"]), 1)

    @unittest.skipUnless(os.name == "posix", "requires a real closed inherited fd1")
    def test_closed_stdout_reports_published_database(self):
        result = self.command(preexec_fn=lambda: os.close(1))
        self.check_new_database(result, receipt=False)
        self.assertEqual(result.stdout, b"")
        self.assertIn(b"database was published; confirmation output failed", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)

    @unittest.skipUnless(Path("/dev/full").exists(), "requires a real full output device")
    def test_full_stdout_reports_published_database(self):
        flags = ["-O"] if sys.flags.optimize else []
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.source_root)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        with open("/dev/full", "wb") as full:
            result = subprocess.run(
                [sys.executable, *flags, "-B", "-m", "fanout_engine.create_ledger",
                 "--plan", str(self.plan_file), "--database", str(self.database)],
                cwd=self.root, env=env, stdout=full, stderr=subprocess.PIPE, timeout=15,
            )
        self.check_new_database(result, receipt=False)
        self.assertIn(b"database was published; confirmation output failed", result.stderr)
        self.assertNotIn(b"Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
