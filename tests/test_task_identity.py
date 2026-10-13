"""Accepted task receipts retain one usable literal identity in SQLite and history."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready
from fanout_engine.ledger import LedgerError


ROUTE = {"model": "model-a", "effort": "low"}


class LiteralTask(str):
    """Any invoked conversion hook would change the caller's literal receipt."""

    calls = []

    def __bool__(self):
        self.calls.append("bool")
        return False

    def strip(self, *args):
        self.calls.append("strip")
        return "invented-nonblank-text"

    def encode(self, *args, **kwargs):
        self.calls.append("encode")
        return b"invented-encoding"

    def __str__(self):
        self.calls.append("str")
        return "invented-string"

    def __eq__(self, other):
        self.calls.append("eq")
        return True

    def __conform__(self, protocol):
        self.calls.append("conform")
        return " "


class AdaptedTask(str):
    calls = []

    def __conform__(self, protocol):
        self.calls.append(protocol)
        return " "


class FalseTask(str):
    def __bool__(self):
        return False


class EqualTask(str):
    calls = []

    def __eq__(self, other):
        self.calls.append(other)
        return True


class MisleadingBlank(str):
    def strip(self, *args):
        return "invented-nonblank-text"


class RecordingHub:
    def __init__(self, receipts):
        self.receipts = receipts
        self.calls = []

    def submit(self, part, **kwargs):
        self.calls.append((part.id, kwargs.copy()))
        return {"task_id": self.receipts[part.id]}


def authored_plan(*ids):
    return Plan.from_dict({"project": "task-identity", "parts": [
        {"id": part_id, "instruction": "Local receipt qualification."}
        for part_id in ids
    ]})


def ready_ledger(ledger, plan):
    ledger.record_plan(plan)
    for part in plan.parts:
        ledger.mark_dispatching(plan.project_id, part.id, "worker-local", ROUTE)


def router():
    return EffortRouter({"model-a": ("low",)}, pool=(Route("model-a", "low"),))


class TaskIdentityTests(unittest.TestCase):
    def test_invalid_receipts_are_refused_before_sql_and_preserve_state(self):
        invalid = (None, "", " \t\n", "\u2003", 7, True, 1.5, b"task-id",
                   ["task-id"], {"task_id": "task-id"}, "\ud800", "task-\udfff",
                   LiteralTask(" \t"), LiteralTask("\ud800"))
        plan = authored_plan("one")
        for task_id in invalid:
            with self.subTest(task_id=repr(task_id)), Ledger() as ledger:
                ready_ledger(ledger, plan)
                before = (ledger.part(plan.project_id, "one"), ledger.events(plan.project_id))
                statements = []
                LiteralTask.calls.clear()
                ledger._db.set_trace_callback(statements.append)
                try:
                    with self.assertRaisesRegex(LedgerError, "task id"):
                        ledger.mark_running(plan.project_id, "one", task_id)
                finally:
                    ledger._db.set_trace_callback(None)
                self.assertEqual(statements, [])
                self.assertEqual(LiteralTask.calls, [])
                self.assertEqual((ledger.part(plan.project_id, "one"),
                                  ledger.events(plan.project_id)), before)

    def test_literal_receipts_survive_storage_events_and_fresh_cli_reads(self):
        values = ("task-id", "  task-雪\t", "task-Ω", "line\nbreak",
                  "task\x00literal", LiteralTask("  task-雪\t"))
        expected = [str.__str__(value) for value in values]
        plan = authored_plan(*(f"part-{index}" for index in range(len(values))))
        with tempfile.TemporaryDirectory(prefix="fanout-task-") as directory:
            database = Path(directory) / "retained.sqlite3"
            with Ledger(str(database)) as ledger:
                ready_ledger(ledger, plan)
                for part, task_id in zip(plan.parts, values):
                    with self.subTest(part=part.id):
                        LiteralTask.calls.clear()
                        ledger.mark_running(plan.project_id, part.id, task_id)
                        before = (ledger.part(plan.project_id, part.id),
                                  ledger.events(plan.project_id))
                        ledger.mark_running(plan.project_id, part.id, task_id)
                        self.assertEqual(LiteralTask.calls, [])
                        self.assertEqual((ledger.part(plan.project_id, part.id),
                                          ledger.events(plan.project_id)), before)
                        self.assertEqual(before[0]["task_id"], str.__str__(task_id))
                        self.assertEqual(before[1][-1]["detail"]["task_id"], str.__str__(task_id))
            original = database.read_bytes()
            reports = {}
            for module in ("inspect", "history"):
                command = [sys.executable, "-B"]
                if sys.flags.optimize:
                    command.append("-O")
                command.extend(["-m", "fanout_engine." + module, "--database", str(database),
                                "--project", plan.project_id])
                result = subprocess.run(command, cwd=Path(__file__).resolve().parents[1],
                                        capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, b"")
                reports[module] = json.loads(result.stdout)
                self.assertEqual(database.read_bytes(), original)
            self.assertEqual([part["task_id"] for part in reports["inspect"]["parts"]], expected)
            self.assertEqual([event["detail"]["task_id"] for event in reports["history"]["events"]
                              if event["event"] == "dispatch_accepted"], expected)

    def test_running_identity_cannot_be_replaced_by_equality_override(self):
        plan = authored_plan("one")
        with Ledger() as ledger:
            ready_ledger(ledger, plan)
            ledger.mark_running(plan.project_id, "one", "accepted-task")
            before = (ledger.part(plan.project_id, "one"), ledger.events(plan.project_id))
            EqualTask.calls.clear()
            with self.assertRaisesRegex(LedgerError, "only a dispatching part"):
                ledger.mark_running(plan.project_id, "one", EqualTask("different-task"))
            self.assertEqual(EqualTask.calls, [])
            self.assertEqual((ledger.part(plan.project_id, "one"), ledger.events(plan.project_id)), before)

    def test_dispatch_keeps_literal_task_ids_and_never_replays_accepted_work(self):
        plan = Plan.from_dict({"project": "task-identity", "parts": [
            {"id": "first", "instruction": "First local receipt."},
            {"id": "second", "instruction": "Independent local receipt."},
            {"id": "dependent", "instruction": "Wait for first.", "depends_on": ["first"]},
        ]})
        receipts = {"first": AdaptedTask("  accepted-雪\t"), "second": FalseTask("accepted-Ω")}
        hub = RecordingHub(receipts)
        AdaptedTask.calls.clear()
        with Ledger() as ledger:
            report = dispatch_ready(plan, ledger, hub, router(), worker_for=lambda _: "worker-local")
            self.assertEqual(report.started, ("first", "second"))
            self.assertEqual(report.outcome_unknown, ())
            self.assertEqual(report.not_ready, ("dependent",))
            self.assertEqual(AdaptedTask.calls, [])
            for part_id, task_id in receipts.items():
                row = ledger.part(plan.project_id, part_id)
                events = ledger.events(plan.project_id, part_id)
                self.assertEqual(row["task_id"], str.__str__(task_id))
                self.assertEqual(events[-1]["detail"]["task_id"], str.__str__(task_id))
                self.assertEqual(row["worker_id"], "worker-local")
                self.assertEqual(row["idempotency_key"], plan.idempotency_key(part_id))
            before = ledger.events(plan.project_id)
            repeated = dispatch_ready(plan, ledger, hub, router(), worker_for=lambda _: "worker-local")
            self.assertEqual(repeated.started, ())
            self.assertEqual(repeated.outcome_unknown, ())
            self.assertEqual(repeated.not_ready, ("dependent",))
            self.assertEqual([part_id for part_id, _ in hub.calls], ["first", "second"])
            self.assertEqual(ledger.events(plan.project_id), before)

    def test_misleading_blank_receipt_is_parked_after_adapter_acceptance(self):
        plan = authored_plan("first", "second")
        hub = RecordingHub({"first": MisleadingBlank(" \t"), "second": "accepted-second"})
        with Ledger() as ledger:
            report = dispatch_ready(plan, ledger, hub, router(), worker_for=lambda _: "worker-local")
            self.assertEqual(report.started, ("second",))
            self.assertEqual(report.outcome_unknown, ("first",))
            self.assertEqual(ledger.part_state(plan.project_id, "first"), "outcome_unknown")
            self.assertIsNone(ledger.part(plan.project_id, "first")["task_id"])
            self.assertEqual([event["event"] for event in ledger.events(plan.project_id, "first")],
                             ["dispatch_started", "outcome_unknown"])
            before = ledger.events(plan.project_id)
            dispatch_ready(plan, ledger, hub, router(), worker_for=lambda _: "worker-local")
            self.assertEqual([part_id for part_id, _ in hub.calls], ["first", "second"])
            self.assertEqual(ledger.events(plan.project_id), before)


if __name__ == "__main__":
    unittest.main()
