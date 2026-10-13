"""Public ledger reads must leave transaction completion to their caller."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fanout_engine import Ledger, Plan
from fanout_engine.ledger import LedgerError


class ReadTransactionOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="fanout-read-owner-")
        self.addCleanup(self.directory.cleanup)
        self.database = str(Path(self.directory.name) / "ledger.sqlite3")
        self.ledger = Ledger(self.database)
        self.addCleanup(self.ledger.close)
        self.observer = sqlite3.connect(self.database, isolation_level=None)
        self.addCleanup(self.observer.close)
        self.plan = Plan.from_dict({"project": "reading", "parts": [
            {"id": "prepare", "instruction": "Prepare fictional source."},
            {"id": "review", "instruction": "Review it.", "depends_on": ["prepare"]},
        ]})
        self.ledger.record_plan(self.plan)
        self.ledger.mark_dispatching(
            "reading", "prepare", "worker-a", {"model": "model-a", "effort": "low"}
        )
        self.ledger.mark_running("reading", "prepare", "task-prepare")
        self.ledger.mark_completed("reading", "prepare", "artifact://fictional")
        self.ledger._db.execute("CREATE TABLE caller_notes(value TEXT NOT NULL)")
        self.ledger._db.execute("INSERT INTO caller_notes VALUES('before')")

    def readers(self):
        return {
            "part_state": lambda: self.ledger.part_state("reading", "prepare"),
            "part": lambda: self.ledger.part("reading", "prepare"),
            "idempotency_key": lambda: self.ledger.idempotency_key("reading", "prepare"),
            "completed_ids": lambda: self.ledger.completed_ids("reading"),
            "dispatchable_ids": lambda: self.ledger.dispatchable_ids("reading"),
            "events": lambda: self.ledger.events("reading"),
            "events_for_part": lambda: self.ledger.events("reading", "prepare"),
        }

    @contextmanager
    def pending_write(self):
        self.ledger._db.rollback()
        self.ledger._db.execute("UPDATE caller_notes SET value='before'")
        self.ledger._db.execute("BEGIN")
        self.ledger._db.execute("UPDATE caller_notes SET value='pending'")
        try:
            yield
        finally:
            self.ledger._db.rollback()

    def assert_pending_is_owned_by_caller(self):
        self.assertTrue(self.ledger._db.in_transaction)
        self.assertEqual(
            self.ledger._db.execute("SELECT value FROM caller_notes").fetchone()[0],
            "pending",
        )
        self.assertEqual(
            self.observer.execute("SELECT value FROM caller_notes").fetchone()[0],
            "before",
        )

    def test_successful_reads_preserve_pending_work_and_rollback_choice(self):
        for name, read in self.readers().items():
            with self.subTest(method=name):
                expected = read()
                with self.pending_write():
                    self.assertEqual(read(), expected)
                    self.assert_pending_is_owned_by_caller()
                self.assertEqual(
                    self.observer.execute("SELECT value FROM caller_notes").fetchone()[0],
                    "before",
                )

    def test_only_explicit_caller_commit_publishes_the_pending_work(self):
        with self.pending_write():
            for read in self.readers().values():
                read()
            self.assert_pending_is_owned_by_caller()
            self.ledger._db.commit()
            self.assertFalse(self.ledger._db.in_transaction)
            self.assertEqual(
                self.observer.execute("SELECT value FROM caller_notes").fetchone()[0],
                "pending",
            )

    def test_missing_part_reads_preserve_pending_work(self):
        for name in ("part_state", "part", "idempotency_key"):
            with self.subTest(method=name), self.pending_write():
                with self.assertRaisesRegex(LedgerError, "part is not in the ledger"):
                    getattr(self.ledger, name)("reading", "missing")
                self.assert_pending_is_owned_by_caller()

    def test_json_read_failures_preserve_pending_work(self):
        cases = [
            ("part", "UPDATE parts SET payload_json='{' WHERE part_id='prepare'",
             lambda: self.ledger.part("reading", "prepare")),
            ("events", "UPDATE events SET detail_json='{' WHERE event='plan_recorded'",
             lambda: self.ledger.events("reading")),
        ]
        for name, statement, read in cases:
            with self.subTest(method=name), self.pending_write():
                self.ledger._db.execute(statement)
                with self.assertRaises(json.JSONDecodeError):
                    read()
                self.assert_pending_is_owned_by_caller()
        self.assertEqual(self.ledger.part("reading", "prepare")["payload"],
                         self.plan.parts[0].to_dict())
        self.assertEqual(len(self.ledger.events("reading")), 4)

    def test_sql_read_failure_preserves_pending_work_and_schema_rollback(self):
        with self.pending_write():
            self.ledger._db.execute("DROP TABLE events")
            with self.assertRaisesRegex(sqlite3.OperationalError, "no such table"):
                self.ledger.events("reading")
            self.assertTrue(self.ledger._db.in_transaction)
            self.assertEqual(
                self.ledger._db.execute("SELECT value FROM caller_notes").fetchone()[0],
                "pending",
            )
        self.assertEqual(len(self.ledger.events("reading")), 4)
        self.assertEqual(
            self.observer.execute("SELECT value FROM caller_notes").fetchone()[0],
            "before",
        )

    def test_readonly_reads_keep_the_callers_snapshot_until_rollback(self):
        # WAL allows another writer to commit while the reader retains its own
        # explicit snapshot. A public read must not silently end that snapshot.
        self.ledger._db.execute("PRAGMA journal_mode=WAL")
        with Ledger.open_readonly(self.database) as reader:
            reader._db.execute("BEGIN")
            self.assertEqual(reader.part_state("reading", "review"), "queued")
            self.assertTrue(reader._db.in_transaction)
            self.ledger.mark_dispatching(
                "reading", "review", "worker-b", {"model": "model-a", "effort": "low"}
            )
            self.assertEqual(reader.part_state("reading", "review"), "queued")
            self.assertTrue(reader._db.in_transaction)
            reader._db.rollback()
            self.assertEqual(reader.part_state("reading", "review"), "dispatching")

    def test_ordinary_reads_do_not_open_a_transaction_or_change_durable_data(self):
        before = self.observer.execute("SELECT * FROM caller_notes").fetchall()
        self.assertFalse(self.ledger._db.in_transaction)
        self.assertEqual(self.ledger.part_state("reading", "prepare"), "completed")
        self.assertEqual(self.ledger.completed_ids("reading"), {"prepare"})
        self.assertEqual(self.ledger.dispatchable_ids("reading"), {"review"})
        self.assertEqual(self.ledger.idempotency_key("reading", "prepare"),
                         self.plan.idempotency_key("prepare"))
        for read in self.readers().values():
            read()
            self.assertFalse(self.ledger._db.in_transaction)
        self.assertEqual(self.observer.execute("SELECT * FROM caller_notes").fetchall(),
                         before)
        with Ledger.open_readonly(self.database) as reader:
            self.assertEqual(reader.part("reading", "prepare"),
                             self.ledger.part("reading", "prepare"))
            self.assertEqual(reader.events("reading"), self.ledger.events("reading"))
            self.assertFalse(reader._db.in_transaction)


if __name__ == "__main__":
    unittest.main()
