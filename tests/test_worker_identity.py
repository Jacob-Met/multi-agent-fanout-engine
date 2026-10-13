"""Worker identity must survive the adapter and SQLite boundary unchanged."""
from pathlib import Path
import tempfile
import unittest

from fanout_engine import EffortRouter, Ledger, LedgerError, Plan, Route, dispatch_ready


ROUTE = {"model": "model-a", "effort": "low"}
INVALID_WORKERS = (
    "", " \t\r\n", "\u00a0\u2003",
    None, False, True, 0, 17, 1.5,
    b"worker-a", ["worker-a"], {"worker": "a"},
    "\ud800", "worker-\udfff",
)


class RecordingHub:
    def __init__(self):
        self.calls = []

    def submit(self, part, *, route, worker_id, idempotency_key):
        self.calls.append((part.id, worker_id, route, idempotency_key))
        return {"task_id": "task-" + part.id}


class LiteralString(str):
    """Overrides must not decide whether the literal identity is valid."""

    def __bool__(self):
        raise AssertionError("worker truthiness was invoked")

    def strip(self, *args, **kwargs):
        raise AssertionError("worker strip override was invoked")

    def encode(self, *args, **kwargs):
        raise AssertionError("worker encode override was invoked")


class WorkerIdentityTests(unittest.TestCase):
    def setUp(self):
        self.plan = Plan.from_dict({
            "project": "worker-validation",
            "parts": [
                {"id": "prepare", "instruction": "Prepare local input."},
                {"id": "review", "instruction": "Review the input.",
                 "depends_on": ["prepare"]},
            ],
        })
        self.router = EffortRouter(
            {"model-a": ("low",)}, pool=(Route("model-a", "low"),),
        )

    def assert_rejected_without_sql(self, worker_id):
        with Ledger() as ledger:
            ledger.record_plan(self.plan)
            before = ledger.part(self.plan.project_id, "prepare")
            events = ledger.events(self.plan.project_id)
            statements = []
            ledger._db.set_trace_callback(statements.append)
            try:
                with self.assertRaises(LedgerError):
                    ledger.mark_dispatching(
                        self.plan.project_id, "prepare", worker_id, ROUTE,
                    )
            finally:
                ledger._db.set_trace_callback(None)
            self.assertEqual(statements, [])
            self.assertEqual(ledger.part(self.plan.project_id, "prepare"), before)
            self.assertEqual(ledger.events(self.plan.project_id), events)

    def test_invalid_literal_identity_is_rejected_before_sql(self):
        for worker_id in INVALID_WORKERS:
            with self.subTest(worker_id=repr(worker_id)):
                self.assert_rejected_without_sql(worker_id)

    def test_string_overrides_cannot_admit_invalid_literal_identity(self):
        for worker_id in (LiteralString(" \t"), LiteralString("worker-\ud800")):
            with self.subTest(worker_id=repr(worker_id)):
                self.assert_rejected_without_sql(worker_id)

    def test_invalid_selected_worker_never_reaches_hub(self):
        for worker_id in INVALID_WORKERS:
            with self.subTest(worker_id=repr(worker_id)), Ledger() as ledger:
                hub = RecordingHub()
                with self.assertRaises(LedgerError):
                    dispatch_ready(
                        self.plan, ledger, hub, self.router,
                        worker_for=lambda _: worker_id,
                    )
                self.assertEqual(hub.calls, [])
                for part in self.plan.parts:
                    row = ledger.part(self.plan.project_id, part.id)
                    self.assertEqual(row["state"], "queued")
                    for name in ("worker_id", "task_id", "route_json"):
                        self.assertIsNone(row[name])
                self.assertEqual(
                    [event["event"] for event in ledger.events(self.plan.project_id)],
                    ["plan_recorded"],
                )

    def test_valid_literal_identity_is_retained_and_reopens_unchanged(self):
        for worker_id in (
            "worker-a", "  worker-\u03a9\U0001f6e0  ",
            LiteralString("  literal-\u6771  "),
        ):
            with self.subTest(worker_id=repr(worker_id)):
                with tempfile.TemporaryDirectory() as directory:
                    database = Path(directory) / "ledger.sqlite3"
                    with Ledger(str(database)) as ledger:
                        hub = RecordingHub()
                        selected = []

                        def worker_for(part):
                            selected.append(part.id)
                            return worker_id

                        report = dispatch_ready(
                            self.plan, ledger, hub, self.router,
                            worker_for=worker_for,
                        )
                        self.assertEqual(report.started, ("prepare",))
                        self.assertEqual(report.not_ready, ("review",))
                        self.assertEqual(selected, ["prepare"])
                        self.assertIs(hub.calls[0][1], worker_id)
                        self.assertEqual(
                            hub.calls[0][3],
                            ledger.idempotency_key(self.plan.project_id, "prepare"),
                        )
                    with Ledger.open_readonly(database) as reopened:
                        row = reopened.part(self.plan.project_id, "prepare")
                        self.assertEqual(row["state"], "running")
                        self.assertEqual(row["worker_id"], worker_id)
                        self.assertIs(type(row["worker_id"]), str)
                        self.assertEqual(row["route"], ROUTE)
                        event = next(
                            event for event in reopened.events(self.plan.project_id)
                            if event["event"] == "dispatch_started"
                        )
                        self.assertEqual(event["detail"]["worker_id"], worker_id)

    def test_later_invalid_worker_preserves_earlier_submission(self):
        plan = Plan.from_dict({
            "project": "sequential-workers",
            "parts": [
                {"id": "first", "instruction": "Run first."},
                {"id": "second", "instruction": "Run second."},
            ],
        })
        with Ledger() as ledger:
            hub = RecordingHub()
            with self.assertRaises(LedgerError):
                dispatch_ready(
                    plan, ledger, hub, self.router,
                    worker_for=lambda part: "worker-a" if part.id == "first" else " ",
                )
            self.assertEqual([call[0] for call in hub.calls], ["first"])
            self.assertEqual(ledger.part_state(plan.project_id, "first"), "running")
            self.assertEqual(ledger.part_state(plan.project_id, "second"), "queued")
            self.assertEqual(ledger.events(plan.project_id, "second"), [])


if __name__ == "__main__":
    unittest.main()
