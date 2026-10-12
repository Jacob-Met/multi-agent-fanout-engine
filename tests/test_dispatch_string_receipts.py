"""Receipt admission must validate the Unicode text SQLite will actually bind."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project


class ReceiptHub:
    def __init__(self, first_task_id):
        self.first_task_id = first_task_id
        self.calls = []

    def submit(self, part, *, route, worker_id, idempotency_key):
        self.calls.append((part.id, idempotency_key))
        return {"task_id": self.first_task_id if part.id == "first" else "local-" + part.id}


class StringReceiptTests(unittest.TestCase):
    def setUp(self):
        self.plan = Plan.from_dict({
            "project": "string-receipts",
            "parts": [
                {"id": "first", "instruction": "Submit the first local task."},
                {"id": "independent", "instruction": "Submit the independent task."},
                {"id": "dependent", "instruction": "Wait for the first task.",
                 "depends_on": ["first"]},
            ],
        })
        self.router = EffortRouter({"local-model": ["low"]},
                                   pool=[Route("local-model", "low")])

    def dispatch(self, ledger, hub):
        return dispatch_ready(self.plan, ledger, hub, self.router,
                              worker_for=lambda part: "local-worker")

    def test_custom_encode_cannot_hide_unstorable_underlying_text(self):
        encode_calls = []

        class MisleadingEncoding(str):
            def encode(self, *args, **kwargs):
                encode_calls.append((args, kwargs))
                return b"apparently-storable"

        for text in ("accepted-\ud800", "accepted-\udfff", "accepted-\ud83e\udded"):
            with self.subTest(text=repr(text)), TemporaryDirectory() as directory:
                database = str(Path(directory) / "retained.sqlite3")
                hub = ReceiptHub(MisleadingEncoding(text))
                with Ledger(database) as ledger:
                    result = self.dispatch(ledger, hub)
                    self.assertEqual(result.started, ("independent",))
                    self.assertEqual(result.outcome_unknown, ("first",))
                    self.assertEqual(result.not_ready, ("dependent",))
                    first = ledger.part(self.plan.project_id, "first")
                    self.assertEqual(first["state"], "outcome_unknown")
                    self.assertIsNone(first["task_id"])
                    self.assertEqual(first["evidence"], {
                        "source": "hub adapter",
                        "locator": self.plan.idempotency_key("first"),
                        "finding": "submit returned no verifiable task identifier",
                    })
                    before = inspect_project(ledger, self.plan.project_id)
                    events = ledger.events(self.plan.project_id)

                with Ledger.open_readonly(database) as ledger:
                    self.assertEqual(inspect_project(ledger, self.plan.project_id), before)
                with Ledger(database) as ledger:
                    self.assertEqual(self.dispatch(ledger, hub).started, ())
                    self.assertEqual(inspect_project(ledger, self.plan.project_id), before)
                    self.assertEqual(ledger.events(self.plan.project_id), events)
                self.assertEqual(hub.calls, [
                    (name, self.plan.idempotency_key(name)) for name in ("first", "independent")
                ])
        self.assertEqual(encode_calls, [])

    def test_custom_encode_cannot_reject_storable_underlying_text(self):
        encode_calls = []

        class RefusingEncoding(str):
            def encode(self, *args, **kwargs):
                encode_calls.append((args, kwargs))
                raise RuntimeError("adapter-specific encoder is unavailable")

        text = "  re\u00e7u-\u6771\u4eac-\U0001f9ed  "
        with TemporaryDirectory() as directory:
            database = str(Path(directory) / "retained.sqlite3")
            hub = ReceiptHub(RefusingEncoding(text))
            with Ledger(database) as ledger:
                result = self.dispatch(ledger, hub)
                self.assertEqual(result.started, ("first", "independent"))
                self.assertEqual(result.outcome_unknown, ())
                self.assertEqual(result.not_ready, ("dependent",))
                self.assertEqual(ledger.part(self.plan.project_id, "first")["task_id"], text)
                self.assertEqual(ledger.events(self.plan.project_id, "first")[-1]["detail"]["task_id"], text)
                before = inspect_project(ledger, self.plan.project_id)
                events = ledger.events(self.plan.project_id)

            with Ledger.open_readonly(database) as ledger:
                self.assertEqual(inspect_project(ledger, self.plan.project_id), before)
            with Ledger(database) as ledger:
                self.assertEqual(self.dispatch(ledger, hub).started, ())
                self.assertEqual(inspect_project(ledger, self.plan.project_id), before)
                self.assertEqual(ledger.events(self.plan.project_id), events)
            self.assertEqual(hub.calls, [
                (name, self.plan.idempotency_key(name)) for name in ("first", "independent")
            ])
        self.assertEqual(encode_calls, [])


if __name__ == "__main__":
    unittest.main()
