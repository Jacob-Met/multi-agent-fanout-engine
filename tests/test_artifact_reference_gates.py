"""Completed states require an actual, text artifact reference.

The gate should reject unusable references before changing retained state or
events. Nonempty Unicode references must be kept byte-for-byte.
"""
import unittest

from fanout_engine import Ledger, LedgerError, Plan


PROJECT = "artifact-gate-course"
EVIDENCE = {"source": "local receiver", "locator": "case-1",
            "finding": "external result was verified"}
ROUTE = {"model": "local", "effort": "low"}


class ArtifactReferenceGateTests(unittest.TestCase):
    def plan(self):
        return Plan.from_dict({"project": PROJECT, "parts": [
            {"id": "one", "instruction": "Produce a real artifact."}
        ]})

    def running(self, ledger):
        ledger.record_plan(self.plan())
        ledger.mark_dispatching(PROJECT, "one", "worker", ROUTE)
        ledger.mark_running(PROJECT, "one", "task-id")

    def unknown(self, ledger):
        ledger.record_plan(self.plan())
        ledger.mark_dispatching(PROJECT, "one", "worker", ROUTE)
        ledger.mark_outcome_unknown(PROJECT, "one", EVIDENCE)

    def test_direct_completion_rejects_unusable_references_without_mutation(self):
        for ref in (None, "", "  \t\n", 17, ["artifact"], b"artifact", chr(0xd800)):
            with self.subTest(ref=repr(ref)), Ledger() as ledger:
                self.running(ledger)
                before = ledger.part(PROJECT, "one")
                events = ledger.events(PROJECT)
                with self.assertRaises(LedgerError):
                    ledger.mark_completed(PROJECT, "one", ref)
                self.assertEqual(ledger.part(PROJECT, "one"), before)
                self.assertEqual(ledger.events(PROJECT), events)
                ledger.mark_completed(PROJECT, "one", "file://valid")
                self.assertEqual(ledger.part_state(PROJECT, "one"), "completed")

    def test_unknown_reconciliation_rejects_unusable_artifacts_without_mutation(self):
        for ref in (None, "", " \u2003\t ", 17, ["artifact"], b"artifact", chr(0xd800)):
            with self.subTest(ref=repr(ref)), Ledger() as ledger:
                self.unknown(ledger)
                before = ledger.part(PROJECT, "one")
                events = ledger.events(PROJECT)
                with self.assertRaises(LedgerError):
                    ledger.reconcile_unknown(PROJECT, "one", verdict="completed",
                                             evidence=EVIDENCE, artifact_ref=ref)
                self.assertEqual(ledger.part(PROJECT, "one"), before)
                self.assertEqual(ledger.events(PROJECT), events)
                ledger.reconcile_unknown(PROJECT, "one", verdict="failed",
                                         evidence=EVIDENCE)
                self.assertEqual(ledger.part_state(PROJECT, "one"), "failed")

    def test_valid_unicode_reference_is_retained_exactly_in_both_paths(self):
        reference = "  drive://artefact-東京-🧭  "
        with Ledger() as ledger:
            self.running(ledger)
            ledger.mark_completed(PROJECT, "one", reference)
            self.assertEqual(ledger.part(PROJECT, "one")["artifact_ref"], reference)
            self.assertEqual(ledger.events(PROJECT)[-1]["detail"]["artifact_ref"], reference)
        with Ledger() as ledger:
            self.unknown(ledger)
            ledger.reconcile_unknown(PROJECT, "one", verdict="completed",
                                     evidence=EVIDENCE, artifact_ref=reference)
            self.assertEqual(ledger.part(PROJECT, "one")["artifact_ref"], reference)
            self.assertEqual(ledger.events(PROJECT)[-1]["detail"]["artifact_ref"], reference)


if __name__ == "__main__":
    unittest.main()
