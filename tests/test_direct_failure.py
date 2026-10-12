"""Known task failures retain evidence without introducing an unknown outcome."""
import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fanout_engine import EffortRouter, Ledger, LedgerError, Plan, Route, dispatch_ready, inspect_project


PROOF = {"source": "authored local worker", "locator": "fixture:build-log/東京",
         "finding": "worker returned a verified terminal exit status 7"}
ROUTE = {"model": "fixture-model", "effort": "low"}


def plan():
    return Plan.from_dict({"project": "known-failure", "parts": [
        {"id": "build", "instruction": "Produce a fictional fixture."},
        {"id": "verify", "instruction": "Inspect the fixture.", "depends_on": ["build"]},
        {"id": "notes", "instruction": "Write independent fixture notes."},
    ]})


def running(ledger, project, part="build"):
    ledger.mark_dispatching(project, part, "fixture-worker", ROUTE)
    ledger.mark_running(project, part, "accepted-task:" + part)


class DirectFailureTests(unittest.TestCase):
    def test_recorded_failure_reopens_with_original_dispatch_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "ledger.sqlite3")
            selected = plan()
            proof = copy.deepcopy(PROOF)
            with Ledger(path) as ledger:
                ledger.record_plan(selected)
                running(ledger, selected.project_id)
                before = ledger.part(selected.project_id, "build")
                ledger.mark_failed(selected.project_id, "build", proof)
                proof["finding"] = "later caller mutation"
            with Ledger.open_readonly(path) as reopened:
                failed = reopened.part(selected.project_id, "build")
                self.assertEqual(failed["state"], "failed")
                self.assertEqual(failed["evidence"], PROOF)
                for key in ("task_id", "worker_id", "route", "payload_json",
                            "payload_digest", "idempotency_key", "artifact_ref"):
                    self.assertEqual(failed[key], before[key])
                events = reopened.events(selected.project_id, "build")
                self.assertEqual([row["event"] for row in events],
                                 ["dispatch_started", "dispatch_accepted", "failed"])
                self.assertEqual(events[-1]["detail"], PROOF)

    def test_failed_dependency_stays_blocked_and_other_work_can_dispatch(self):
        class LocalHub:
            calls = []
            def submit(self, part, **kwargs):
                self.calls.append(part.id)
                return {"task_id": "task:" + part.id}
        selected = plan()
        with Ledger() as ledger:
            ledger.record_plan(selected)
            running(ledger, selected.project_id)
            ledger.mark_failed(selected.project_id, "build", PROOF)
            hub = LocalHub()
            router = EffortRouter({"fixture-model": ("low",)}, pool=(Route("fixture-model", "low"),))
            report = dispatch_ready(selected, ledger, hub, router, worker_for=lambda part: "fixture-worker")
            self.assertEqual(report.started, ("notes",))
            self.assertEqual(report.not_ready, ("verify",))
            self.assertEqual(report.outcome_unknown, ())
            again = dispatch_ready(selected, ledger, hub, router, worker_for=lambda part: "fixture-worker")
            self.assertEqual(again.started, ())
            self.assertEqual(hub.calls, ["notes"])
            inspected = inspect_project(ledger, selected.project_id)
            self.assertEqual(inspected["state_counts"]["failed"], 1)
            self.assertEqual(inspected["blocked_queued_ids"], ["verify"])
            self.assertEqual(inspected["queued_ready_ids"], [])

    def test_each_nonrunning_state_refuses_without_new_events(self):
        for state in ("queued", "dispatching", "outcome_unknown", "completed", "failed"):
            with self.subTest(state=state), Ledger() as ledger:
                selected = plan()
                ledger.record_plan(selected)
                if state != "queued":
                    ledger.mark_dispatching(selected.project_id, "build", "fixture-worker", ROUTE)
                if state in ("outcome_unknown", "completed", "failed"):
                    ledger.mark_running(selected.project_id, "build", "accepted-task")
                if state in ("outcome_unknown", "failed"):
                    ledger.mark_outcome_unknown(selected.project_id, "build", PROOF)
                if state == "completed":
                    ledger.mark_completed(selected.project_id, "build", "fixture:artifact", PROOF)
                if state == "failed":
                    ledger.reconcile_unknown(selected.project_id, "build", verdict="failed", evidence=PROOF)
                before = ledger.part(selected.project_id, "build"), ledger.events(selected.project_id)
                with self.assertRaises(LedgerError):
                    ledger.mark_failed(selected.project_id, "build", PROOF)
                self.assertEqual((ledger.part(selected.project_id, "build"), ledger.events(selected.project_id)), before)

    def test_evidence_is_required_and_invalid_evidence_preserves_running_state(self):
        invalid = [None, [], {}, {**PROOF, "source": ""}, {**PROOF, "locator": " \t"},
                   {**PROOF, "finding": 7}, {"source": "test", "locator": "test"}]
        with Ledger() as ledger:
            selected = plan()
            ledger.record_plan(selected)
            running(ledger, selected.project_id)
            before = ledger.part(selected.project_id, "build"), ledger.events(selected.project_id)
            for proof in invalid:
                with self.subTest(proof=proof), self.assertRaises(LedgerError):
                    ledger.mark_failed(selected.project_id, "build", proof)
                self.assertEqual((ledger.part(selected.project_id, "build"), ledger.events(selected.project_id)), before)

    def test_unknown_project_or_part_refuses_and_existing_project_is_exact(self):
        with Ledger() as ledger:
            selected = plan()
            ledger.record_plan(selected)
            running(ledger, selected.project_id)
            before = inspect_project(ledger, selected.project_id), ledger.events(selected.project_id)
            for project, part in (("missing-project", "build"), (selected.project_id, "missing-part")):
                with self.subTest(project=project, part=part), self.assertRaises(LedgerError):
                    ledger.mark_failed(project, part, PROOF)
                self.assertEqual((inspect_project(ledger, selected.project_id), ledger.events(selected.project_id)), before)

    def test_failed_journal_write_rolls_back_then_the_same_result_can_be_recorded(self):
        with Ledger() as ledger:
            selected = plan()
            ledger.record_plan(selected)
            running(ledger, selected.project_id)
            ledger._db.execute("""CREATE TRIGGER reject_failure_event BEFORE INSERT ON events
                WHEN NEW.event = 'failed' BEGIN SELECT RAISE(ABORT, 'fixture journal refusal'); END""")
            before = ledger.part(selected.project_id, "build"), ledger.events(selected.project_id)
            with self.assertRaisesRegex(sqlite3.IntegrityError, "fixture journal refusal"):
                ledger.mark_failed(selected.project_id, "build", PROOF)
            self.assertFalse(ledger._db.in_transaction)
            self.assertEqual((ledger.part(selected.project_id, "build"), ledger.events(selected.project_id)), before)
            ledger._db.execute("DROP TRIGGER reject_failure_event")
            ledger.mark_failed(selected.project_id, "build", PROOF)
            self.assertEqual(ledger.part_state(selected.project_id, "build"), "failed")
            self.assertEqual([e["event"] for e in ledger.events(selected.project_id, "build")].count("failed"), 1)


if __name__ == "__main__":
    unittest.main()
