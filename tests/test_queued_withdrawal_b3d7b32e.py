"""Withdraw unsubmitted queued work while preserving dispatch and ledger contracts."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import EffortRouter, Ledger, LedgerError, Plan, Route, dispatch_ready, inspect_project

PROOF = {"source": "local caller decision", "locator": "fixture:request/東京",
         "finding": "  This authored work is no longer requested.  ", "note": "kept"}
ROUTE = {"model": "fixture", "effort": "low"}


def make_plan():
    return Plan.from_dict({"project": "withdraw-fixture", "parts": [
        {"id": "build", "instruction": "Prepare authored work."},
        {"id": "verify", "instruction": "Receive work.", "depends_on": ["build"]},
        {"id": "notes", "instruction": "Prepare independent notes."},
    ]})


def snapshot(ledger):
    return tuple(tuple(tuple(row) for row in ledger._db.execute(query)) for query in (
        "SELECT * FROM projects ORDER BY project_id",
        "SELECT * FROM parts ORDER BY project_id,part_id",
        "SELECT * FROM events ORDER BY seq",
        "SELECT * FROM sqlite_sequence ORDER BY name",
    ))


class LocalHub:
    def __init__(self):
        self.calls = []

    def submit(self, part, **kwargs):
        self.calls.append(part.id)
        return {"task_id": "local:" + part.id}


def dispatch(plan, ledger, hub, worker_for=lambda part: "fixture-worker"):
    router = EffortRouter({"fixture": ("low",)}, pool=(Route("fixture", "low"),))
    return dispatch_ready(plan, ledger, hub, router, worker_for=worker_for)


class QueuedWithdrawalTests(unittest.TestCase):
    def setUp(self):
        self.plan = make_plan()
        self.ledger = Ledger()
        self.addCleanup(self.ledger.close)
        self.ledger.record_plan(self.plan)

    def withdraw(self, part="build", evidence=PROOF):
        self.ledger.withdraw_queued(self.plan.project_id, part, evidence)

    def test_withdrawal_preserves_identity_and_detaches_required_evidence(self):
        before = self.ledger.part(self.plan.project_id, "build")
        proof = copy.deepcopy(PROOF)
        self.withdraw(evidence=proof)
        proof["finding"] = "later caller mutation"
        after = self.ledger.part(self.plan.project_id, "build")
        self.assertEqual(after["state"], "failed")
        self.assertEqual(after["evidence"], PROOF)
        changed = {"state", "evidence_json", "updated_at"}
        for key, value in before.items():
            if key not in changed:
                self.assertEqual(after[key], value, key)
        for key in ("worker_id", "task_id", "route_json", "artifact_ref"):
            self.assertIsNone(after[key])
        events = self.ledger.events(self.plan.project_id, "build")
        self.assertEqual([row["event"] for row in events], ["queued_withdrawn"])
        self.assertEqual(events[0]["detail"], PROOF)
        self.assertEqual(events[0]["detail_json"], after["evidence_json"])

    def test_withdrawn_dependency_stays_blocked_and_independent_work_runs_once(self):
        self.withdraw()
        hub = LocalHub()
        first = dispatch(self.plan, self.ledger, hub)
        second = dispatch(self.plan, self.ledger, hub)
        self.assertEqual(first.started, ("notes",))
        self.assertEqual(first.not_ready, ("verify",))
        self.assertEqual(second.started, ())
        self.assertEqual(hub.calls, ["notes"])
        report = inspect_project(self.ledger, self.plan.project_id)
        self.assertEqual(report["blocked_queued_ids"], ["verify"])
        self.assertEqual(report["queued_ready_ids"], [])
        self.assertEqual(report["state_counts"],
                         {"queued": 1, "dispatching": 0, "running": 1,
                          "outcome_unknown": 0, "completed": 0, "failed": 1})

    def test_queued_work_can_be_withdrawn_before_its_dependencies_complete(self):
        self.withdraw("verify")
        hub = LocalHub()
        result = dispatch(self.plan, self.ledger, hub)
        self.assertEqual(result.started, ("build", "notes"))
        self.assertEqual(result.not_ready, ())
        self.assertEqual(self.ledger.part_state(self.plan.project_id, "verify"), "failed")
        self.assertEqual([event["event"] for event in self.ledger.events(self.plan.project_id, "verify")],
                         ["queued_withdrawn"])

    def test_other_states_refuse_without_mutation(self):
        for state in ("dispatching", "running", "outcome_unknown", "completed", "failed"):
            with self.subTest(state=state), Ledger() as ledger:
                ledger.record_plan(self.plan)
                ledger.mark_dispatching(self.plan.project_id, "build", "worker", ROUTE)
                if state != "dispatching":
                    ledger.mark_running(self.plan.project_id, "build", "task")
                if state == "outcome_unknown":
                    ledger.mark_outcome_unknown(self.plan.project_id, "build", PROOF)
                elif state == "completed":
                    ledger.mark_completed(self.plan.project_id, "build", "fixture:artifact", PROOF)
                elif state == "failed":
                    ledger.mark_failed(self.plan.project_id, "build", PROOF)
                before = snapshot(ledger)
                with self.assertRaisesRegex(LedgerError, "only queued"):
                    ledger.withdraw_queued(self.plan.project_id, "build", PROOF)
                self.assertEqual(snapshot(ledger), before)
                self.assertFalse(ledger._db.in_transaction)

    def test_repeat_and_unknown_references_refuse_without_mutation(self):
        self.withdraw()
        before = snapshot(self.ledger)
        for project, part in ((self.plan.project_id, "build"), ("missing", "build"),
                              (self.plan.project_id, "missing")):
            with self.subTest(project=project, part=part), self.assertRaises(LedgerError):
                self.ledger.withdraw_queued(project, part, PROOF)
            self.assertEqual(snapshot(self.ledger), before)

    def test_invalid_evidence_refuses_before_mutation(self):
        before = snapshot(self.ledger)
        invalid = [None, [], {}, {**PROOF, "source": ""}, {**PROOF, "locator": " \t"},
                   {**PROOF, "finding": 7}, {"source": "test", "locator": "test"}]
        for proof in invalid:
            with self.subTest(proof=proof), self.assertRaises(LedgerError):
                self.withdraw(evidence=proof)
            self.assertEqual(snapshot(self.ledger), before)

    def test_non_json_extra_evidence_refuses_without_mutation(self):
        before = snapshot(self.ledger)
        with self.assertRaises(ValueError):
            self.withdraw(evidence={**PROOF, "extra": float("nan")})
        self.assertEqual(snapshot(self.ledger), before)
        self.assertFalse(self.ledger._db.in_transaction)

    def test_any_nonnull_submission_or_artifact_reference_refuses(self):
        for column in ("worker_id", "task_id", "route_json", "artifact_ref"):
            for value in ("", "retained-reference"):
                with self.subTest(column=column, value=value), Ledger() as ledger:
                    ledger.record_plan(self.plan)
                    ledger._db.execute(f"UPDATE parts SET {column}=? WHERE part_id='build'", (value,))
                    before = snapshot(ledger)
                    with self.assertRaisesRegex(LedgerError, "references"):
                        ledger.withdraw_queued(self.plan.project_id, "build", PROOF)
                    self.assertEqual(snapshot(ledger), before)

    def test_event_insert_failure_rolls_back_entire_withdrawal(self):
        self.ledger._db.execute("""CREATE TRIGGER reject_withdrawal BEFORE INSERT ON events
            WHEN NEW.event='queued_withdrawn'
            BEGIN SELECT RAISE(ABORT, 'authored journal refusal'); END""")
        before = snapshot(self.ledger)
        with self.assertRaisesRegex(sqlite3.IntegrityError, "authored journal refusal"):
            self.withdraw()
        self.assertEqual(snapshot(self.ledger), before)
        self.assertFalse(self.ledger._db.in_transaction)
        self.ledger._db.execute("DROP TRIGGER reject_withdrawal")
        self.withdraw()
        self.assertEqual(len(self.ledger.events(self.plan.project_id, "build")), 1)

    def test_existing_caller_transaction_is_not_rolled_back_or_committed(self):
        self.ledger._db.execute("BEGIN")
        self.ledger._db.execute("UPDATE parts SET updated_at=123 WHERE part_id='notes'")
        before = snapshot(self.ledger)
        with self.assertRaises(sqlite3.OperationalError):
            self.withdraw()
        self.assertTrue(self.ledger._db.in_transaction)
        self.assertEqual(snapshot(self.ledger), before)
        self.ledger._db.rollback()
        self.assertNotEqual(snapshot(self.ledger), before)
        self.assertEqual(self.ledger.part_state(self.plan.project_id, "build"), "queued")

    def test_withdrawal_wins_after_dispatch_readiness_but_before_admission(self):
        hub = LocalHub()
        def withdraw_before_admission(part):
            self.withdraw(part.id)
            return "fixture-worker"
        with self.assertRaises(LedgerError):
            dispatch(self.plan, self.ledger, hub, worker_for=withdraw_before_admission)
        self.assertEqual(hub.calls, [])
        self.assertEqual(self.ledger.part_state(self.plan.project_id, "build"), "failed")
        self.assertEqual([e["event"] for e in self.ledger.events(self.plan.project_id, "build")],
                         ["queued_withdrawn"])

    def test_dispatch_admission_wins_and_withdrawal_preserves_its_identity(self):
        self.ledger.mark_dispatching(self.plan.project_id, "build", "retained-worker", ROUTE)
        before = snapshot(self.ledger)
        with self.assertRaises(LedgerError):
            self.withdraw()
        self.assertEqual(snapshot(self.ledger), before)
        self.ledger.mark_running(self.plan.project_id, "build", "retained-task")
        self.assertEqual(self.ledger.part(self.plan.project_id, "build")["task_id"], "retained-task")

    def test_reopen_preserves_six_state_schema_and_terminal_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            database = str(Path(directory) / "work.sqlite3")
            with Ledger(database) as first:
                first.record_plan(self.plan)
                schema = first._db.execute("SELECT type,name,sql FROM sqlite_master ORDER BY type,name").fetchall()
                schema = [tuple(row) for row in schema]
            with Ledger(database) as second:
                second.withdraw_queued(self.plan.project_id, "build", PROOF)
            with Ledger(database) as reopened:
                current = [tuple(row) for row in reopened._db.execute(
                    "SELECT type,name,sql FROM sqlite_master ORDER BY type,name")]
                self.assertEqual(current, schema)
                self.assertEqual(reopened.part(self.plan.project_id, "build")["evidence"], PROOF)
                hub = LocalHub()
                self.assertEqual(dispatch(self.plan, reopened, hub).started, ("notes",))
                self.assertEqual(hub.calls, ["notes"])
            with Ledger.open_readonly(database) as readonly:
                self.assertEqual(readonly.part_state(self.plan.project_id, "build"), "failed")
                self.assertEqual(inspect_project(readonly, self.plan.project_id)["blocked_queued_ids"], ["verify"])

    def test_local_example_exits_with_no_submission_and_blocked_descendant(self):
        script = Path(__file__).resolve().parents[1] / "examples" / "withdraw_queue.py"
        command = [sys.executable, "-B"]
        if sys.flags.optimize:
            command.append("-O")
        result = subprocess.run(command + [str(script)], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        report = json.loads(result.stdout)
        self.assertEqual(report["submissions"], [])
        self.assertEqual(report["dispatch"]["started"], [])
        self.assertEqual(report["dispatch"]["not_ready"], ["verify"])
        self.assertEqual(report["events"], ["queued_withdrawn"])
        self.assertEqual(report["project"]["state_counts"]["failed"], 1)
        self.assertEqual(report["project"]["blocked_queued_ids"], ["verify"])


if __name__ == "__main__":
    unittest.main()
