"""Interrupted writes must not escape through a later public ledger read."""
import unittest
from unittest.mock import patch

from fanout_engine import Ledger, Plan


class LedgerInterruptionTests(unittest.TestCase):
    def setUp(self):
        self.plan = Plan.from_dict({"project": "interrupted-project", "parts": [
            {"id": "first", "instruction": "Complete the first part."},
            {"id": "second", "instruction": "Complete the second part."},
        ]})
        self.route = {"model": "model-a", "effort": "low"}

    def test_incomplete_plan_is_rolled_back_and_can_be_recorded_again(self):
        for exception_type in (KeyboardInterrupt, SystemExit, GeneratorExit, RuntimeError):
            with self.subTest(exception=exception_type.__name__), Ledger() as ledger:
                interruption = exception_type("stop before the second part")
                with patch("fanout_engine.ledger.time.time", side_effect=[1.0, interruption]):
                    with self.assertRaises(exception_type) as raised:
                        ledger.record_plan(self.plan)

                self.assertIs(raised.exception, interruption)
                self.assertIsNone(ledger.project_snapshot(self.plan.project_id))
                self.assertEqual(ledger.events(self.plan.project_id), [])
                self.assertTrue(ledger.record_plan(self.plan))
                self.assertEqual(ledger.dispatchable_ids(self.plan.project_id), {"first", "second"})
                self.assertEqual(len(ledger.events(self.plan.project_id)), 1)

    def test_interrupted_dispatch_admission_does_not_commit_on_read(self):
        with Ledger() as ledger:
            ledger.record_plan(self.plan)
            before = ledger.part(self.plan.project_id, "first")
            events_before = ledger.events(self.plan.project_id)
            with patch("fanout_engine.ledger.time.time",
                       side_effect=[2.0, KeyboardInterrupt("stop before the event")]):
                with self.assertRaises(KeyboardInterrupt):
                    ledger.mark_dispatching(self.plan.project_id, "first", "worker-a", self.route)

            self.assertEqual(ledger.part_state(self.plan.project_id, "first"), "queued")
            self.assertEqual(ledger.part(self.plan.project_id, "first"), before)
            self.assertEqual(ledger.events(self.plan.project_id), events_before)
            ledger.mark_dispatching(self.plan.project_id, "first", "worker-a", self.route)
            self.assertEqual(ledger.part_state(self.plan.project_id, "first"), "dispatching")

    def test_interrupted_acknowledgement_remains_inflight_for_recovery(self):
        with Ledger() as ledger:
            ledger.record_plan(self.plan)
            ledger.mark_dispatching(self.plan.project_id, "first", "worker-a", self.route)
            before = ledger.part(self.plan.project_id, "first")
            events_before = ledger.events(self.plan.project_id)
            with patch("fanout_engine.ledger.time.time",
                       side_effect=[3.0, SystemExit("stop before the acceptance event")]):
                with self.assertRaises(SystemExit):
                    ledger.mark_running(self.plan.project_id, "first", "task-first")

            self.assertEqual(ledger.part_state(self.plan.project_id, "first"), "dispatching")
            self.assertEqual(ledger.part(self.plan.project_id, "first"), before)
            self.assertEqual(ledger.events(self.plan.project_id), events_before)
            self.assertNotIn("first", ledger.dispatchable_ids(self.plan.project_id))
            self.assertEqual(ledger.mark_interrupted_dispatches_unknown(self.plan.project_id), 1)
            self.assertEqual(ledger.part_state(self.plan.project_id, "first"), "outcome_unknown")
            self.assertNotIn("first", ledger.dispatchable_ids(self.plan.project_id))


if __name__ == "__main__":
    unittest.main()
