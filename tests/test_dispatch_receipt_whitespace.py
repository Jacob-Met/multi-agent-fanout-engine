"""Task receipt admission uses the literal text retained by SQLite."""
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project


class ReceiptHub:
    def __init__(self, receipt):
        self.receipt = receipt
        self.calls = []

    def submit(self, part, *, route, worker_id, idempotency_key):
        self.calls.append((part.id, idempotency_key))
        return {"task_id": self.receipt if part.id == "first" else "local-" + part.id}


class ReceiptWhitespaceTests(unittest.TestCase):
    def setUp(self):
        self.plan = Plan.from_dict({"project": "literal-receipts", "parts": [
            {"id": "first", "instruction": "Receive the authored task reference."},
            {"id": "independent", "instruction": "Continue independent work."},
            {"id": "dependent", "instruction": "Wait for the first task.",
             "depends_on": ["first"]},
        ]})
        self.router = EffortRouter(
            {"local-model": ["low"]}, pool=[Route("local-model", "low")],
        )

    def dispatch(self, ledger, hub):
        return dispatch_ready(
            self.plan, ledger, hub, self.router, worker_for=lambda part: "local-worker",
        )

    def receive(self, receipt, accepted_literal):
        hub = ReceiptHub(receipt)
        unknown = accepted_literal is None
        with TemporaryDirectory(prefix="fanout-literal-receipt-") as directory:
            path = Path(directory) / "dispatch.sqlite3"
            with Ledger(str(path)) as ledger:
                report = self.dispatch(ledger, hub)
                self.assertEqual(report.started,
                                 ("independent",) if unknown else ("first", "independent"))
                self.assertEqual(report.outcome_unknown, ("first",) if unknown else ())
                self.assertEqual(report.not_ready, ("dependent",))
                row = ledger.part(self.plan.project_id, "first")
                self.assertEqual(row["state"], "outcome_unknown" if unknown else "running")
                self.assertEqual(row["task_id"], accepted_literal)
                self.assertEqual(row["idempotency_key"], self.plan.idempotency_key("first"))
                self.assertEqual(row["worker_id"], "local-worker")
                self.assertEqual(row["route"], {"model": "local-model", "effort": "low"})
                first_events = ledger.events(self.plan.project_id, "first")
                self.assertEqual([event["event"] for event in first_events],
                                 ["dispatch_started", "outcome_unknown" if unknown
                                  else "dispatch_accepted"])
                if unknown:
                    self.assertEqual(row["evidence"], {
                        "source": "hub adapter",
                        "locator": self.plan.idempotency_key("first"),
                        "finding": "submit returned no verifiable task identifier",
                    })
                else:
                    self.assertIsNone(row["evidence_json"])
                    self.assertEqual(first_events[-1]["detail"]["task_id"], accepted_literal)
                snapshot = inspect_project(ledger, self.plan.project_id)
                events = ledger.events(self.plan.project_id)

            with closing(sqlite3.connect(path)) as raw:
                self.assertEqual(
                    raw.execute("SELECT task_id FROM parts WHERE project_id=? AND part_id='first'",
                                (self.plan.project_id,)).fetchone()[0],
                    accepted_literal,
                )
            saved_bytes = path.read_bytes()
            with Ledger.open_readonly(path) as reader:
                self.assertEqual(inspect_project(reader, self.plan.project_id), snapshot)
            self.assertEqual(path.read_bytes(), saved_bytes)
            with Ledger(str(path)) as reopened:
                self.assertEqual(self.dispatch(reopened, hub).started, ())
                self.assertEqual(inspect_project(reopened, self.plan.project_id), snapshot)
                self.assertEqual(reopened.events(self.plan.project_id), events)
            self.assertEqual(hub.calls, [
                (part, self.plan.idempotency_key(part)) for part in ("first", "independent")
            ])

    def test_custom_strip_cannot_accept_whitespace_only_text(self):
        calls = []

        class InventedReference(str):
            def strip(self, *args, **kwargs):
                calls.append("strip")
                return "invented-reference"

        for literal in (" ", "\t\r\n", "\u00a0\u2003"):
            with self.subTest(literal=repr(literal)):
                self.receive(InventedReference(literal), None)
        self.assertEqual(calls, [])

    def test_custom_strip_cannot_hide_a_valid_literal_reference(self):
        calls = []

        class HiddenReference(str):
            def strip(self, *args, **kwargs):
                calls.append("strip")
                return ""

        literal = "  re\u00e7u-\u6771\u4eac-\U0001f9ed\t"
        self.receive(HiddenReference(literal), literal)
        self.assertEqual(calls, [])

    def test_custom_strip_exception_does_not_reject_a_valid_literal_reference(self):
        calls = []

        class RefusingStrip(str):
            def strip(self, *args, **kwargs):
                calls.append("strip")
                raise ValueError("adapter validation override")

        literal = "\n  local-task  \u2003"
        self.receive(RefusingStrip(literal), literal)
        self.assertEqual(calls, [])

    def test_ordinary_whitespace_and_unicode_controls_keep_existing_results(self):
        for literal, expected in (("", None), (" \t", None),
                                  ("\u00a0\u2003", None),
                                  ("  task-\u6771\u4eac-\U0001f9ed  ",
                                   "  task-\u6771\u4eac-\U0001f9ed  ")):
            with self.subTest(literal=repr(literal)):
                self.receive(literal, expected)


if __name__ == "__main__":
    unittest.main()
