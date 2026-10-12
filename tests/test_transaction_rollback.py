"""Failed ledger operations must not be committed by a later ordinary read."""
import asyncio
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fanout_engine import Ledger, Plan


class TransactionRollbackTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="fanout-rollback-")
        self.addCleanup(self.directory.cleanup)
        self.database = str(Path(self.directory.name) / "ledger.sqlite3")
        self.ledger = Ledger(self.database)
        self.addCleanup(self.ledger.close)
        self.plan = Plan.from_dict({"project": "rollback", "parts": [
            {"id": "prepare", "instruction": "Prepare the source."},
            {"id": "review", "instruction": "Review it.", "depends_on": ["prepare"]},
        ]})

    def persisted_counts(self):
        with sqlite3.connect(self.database) as reader:
            return tuple(reader.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                         for table in ("projects", "parts", "events"))

    def interrupt_after_event(self, failure):
        original_event = self.ledger._event

        def interrupt(*args, **kwargs):
            original_event(*args, **kwargs)
            raise failure

        return patch.object(self.ledger, "_event", side_effect=interrupt)

    def assert_cancelled_plan_is_not_persisted(self, failure):
        with self.interrupt_after_event(failure):
            with self.assertRaises(type(failure)) as caught:
                self.ledger.record_plan(self.plan)
        self.assertIs(caught.exception, failure)
        left_transaction = self.ledger._db.in_transaction
        queued = self.ledger.dispatchable_ids(self.plan.project_id)
        self.assertFalse(left_transaction)
        self.assertEqual(queued, set())
        self.assertEqual(self.persisted_counts(), (0, 0, 0))
        self.assertTrue(self.ledger.record_plan(self.plan))
        self.assertEqual(self.persisted_counts(), (1, 2, 1))

    def test_keyboard_interrupt_does_not_leak_plan_writes(self):
        self.assert_cancelled_plan_is_not_persisted(KeyboardInterrupt("cancel"))

    def test_system_exit_does_not_leak_plan_writes(self):
        self.assert_cancelled_plan_is_not_persisted(SystemExit(7))

    def test_generator_exit_does_not_leak_plan_writes(self):
        self.assert_cancelled_plan_is_not_persisted(GeneratorExit())

    def test_async_cancellation_does_not_leak_plan_writes(self):
        self.assert_cancelled_plan_is_not_persisted(asyncio.CancelledError())

    def test_cancelled_transition_keeps_previous_state_and_events(self):
        self.ledger.record_plan(self.plan)
        before = self.ledger.part(self.plan.project_id, "prepare")
        before_events = self.ledger.events(self.plan.project_id)
        failure = KeyboardInterrupt("cancel dispatch recording")
        with self.interrupt_after_event(failure):
            with self.assertRaises(KeyboardInterrupt) as caught:
                self.ledger.mark_dispatching(self.plan.project_id, "prepare", "worker-a",
                                              {"model": "model-a", "effort": "low"})
        self.assertIs(caught.exception, failure)
        left_transaction = self.ledger._db.in_transaction
        after = self.ledger.part(self.plan.project_id, "prepare")
        self.assertFalse(left_transaction)
        self.assertEqual(after, before)
        self.assertEqual(self.ledger.events(self.plan.project_id), before_events)
        self.assertEqual(self.persisted_counts(), (1, 2, 1))

    def test_ordinary_body_failure_still_rolls_back(self):
        failure = ValueError("event could not be encoded")
        with self.interrupt_after_event(failure):
            with self.assertRaises(ValueError) as caught:
                self.ledger.record_plan(self.plan)
        self.assertIs(caught.exception, failure)
        self.assertFalse(self.ledger._db.in_transaction)
        self.assertEqual(self.ledger.completed_ids(self.plan.project_id), set())
        self.assertEqual(self.persisted_counts(), (0, 0, 0))

    def hold_reader(self):
        # A real rollback-journal reader permits BEGIN IMMEDIATE and writes,
        # but prevents the writer from obtaining the lock required by COMMIT.
        reader = sqlite3.connect(self.database, isolation_level=None)
        self.addCleanup(reader.close)
        reader.execute("BEGIN")
        reader.execute("SELECT * FROM projects").fetchall()
        self.ledger._db.execute("PRAGMA busy_timeout=0")
        return reader

    def test_failed_commit_is_not_persisted_by_a_later_read(self):
        reader = self.hold_reader()
        try:
            with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                self.ledger.record_plan(self.plan)
            left_transaction = self.ledger._db.in_transaction
        finally:
            reader.rollback()
        queued = self.ledger.dispatchable_ids(self.plan.project_id)
        self.assertFalse(left_transaction)
        self.assertEqual(queued, set())
        self.assertEqual(self.persisted_counts(), (0, 0, 0))
        self.assertTrue(self.ledger.record_plan(self.plan))
        self.assertEqual(self.persisted_counts(), (1, 2, 1))

    def test_failed_transition_commit_preserves_state_and_can_retry(self):
        self.ledger.record_plan(self.plan)
        before = self.ledger.part(self.plan.project_id, "prepare")
        events = self.ledger.events(self.plan.project_id)
        reader = self.hold_reader()
        try:
            with self.assertRaisesRegex(sqlite3.OperationalError, "locked"):
                self.ledger.mark_dispatching(self.plan.project_id, "prepare", "worker-a",
                                              {"model": "model-a", "effort": "low"})
            left_transaction = self.ledger._db.in_transaction
        finally:
            reader.rollback()
        after = self.ledger.part(self.plan.project_id, "prepare")
        self.assertFalse(left_transaction)
        self.assertEqual(after, before)
        self.assertEqual(self.ledger.events(self.plan.project_id), events)
        self.ledger.mark_dispatching(self.plan.project_id, "prepare", "worker-a",
                                      {"model": "model-a", "effort": "low"})
        self.assertEqual(self.ledger.part_state(self.plan.project_id, "prepare"), "dispatching")
        self.assertEqual(self.persisted_counts(), (1, 2, 2))

    def test_failed_begin_does_not_rollback_callers_existing_transaction(self):
        self.ledger.record_plan(self.plan)
        self.ledger._db.execute("BEGIN")
        self.ledger._db.execute("UPDATE parts SET worker_id='caller-owned' WHERE part_id='prepare'")
        with self.assertRaisesRegex(sqlite3.OperationalError, "within a transaction"):
            self.ledger.mark_dispatching(self.plan.project_id, "prepare", "worker-a", {})
        self.assertTrue(self.ledger._db.in_transaction)
        row = self.ledger._db.execute("SELECT worker_id FROM parts WHERE part_id='prepare'").fetchone()
        self.assertEqual(row[0], "caller-owned")
        with sqlite3.connect(self.database) as reader:
            self.assertIsNone(reader.execute("SELECT worker_id FROM parts WHERE part_id='prepare'").fetchone()[0])
        self.ledger._db.rollback()
        self.assertIsNone(self.ledger.part(self.plan.project_id, "prepare")["worker_id"])

    def test_successful_lifecycle_remains_durable_and_idempotent(self):
        self.assertTrue(self.ledger.record_plan(self.plan))
        self.assertFalse(self.ledger.record_plan(self.plan))
        self.ledger.mark_dispatching(self.plan.project_id, "prepare", "worker-a",
                                      {"model": "model-a", "effort": "low"})
        self.ledger.mark_running(self.plan.project_id, "prepare", "task-prepare")
        self.ledger.mark_running(self.plan.project_id, "prepare", "task-prepare")
        self.ledger.mark_completed(self.plan.project_id, "prepare", "artifact://prepare")
        self.assertFalse(self.ledger._db.in_transaction)
        with Ledger(self.database) as reopened:
            self.assertEqual(reopened.completed_ids(self.plan.project_id), {"prepare"})
            self.assertEqual(reopened.dispatchable_ids(self.plan.project_id), {"review"})
            self.assertEqual(reopened.idempotency_key(self.plan.project_id, "prepare"),
                             self.plan.idempotency_key("prepare"))
            self.assertEqual([event["event"] for event in reopened.events(self.plan.project_id)],
                             ["plan_recorded", "dispatch_started", "dispatch_accepted", "completed"])


if __name__ == "__main__":
    unittest.main()
