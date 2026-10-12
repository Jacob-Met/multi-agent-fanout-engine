"""Exercise adapter acknowledgements through dispatch and a reopened SQLite ledger."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project


class ReceiptHub:
    def __init__(self, first_response):
        self.first_response = first_response
        self.calls = []

    def submit(self, part, *, route, worker_id, idempotency_key):
        self.calls.append((part.id, idempotency_key))
        if part.id == "first":
            return self.first_response
        return {"task_id": "local-" + part.id}


class UnicodeReceiptTests(unittest.TestCase):
    def setUp(self):
        self.plan = Plan.from_dict({
            "project": "receipt-check",
            "parts": [
                {"id": "first", "instruction": "Run the first independent part."},
                {"id": "later", "instruction": "Run a later independent part."},
                {"id": "dependent", "instruction": "Wait for the first result.",
                 "depends_on": ["first"]},
            ],
        })
        self.router = EffortRouter(
            {"model-a": ("low",)}, pool=(Route("model-a", "low"),),
        )

    def dispatch(self, ledger, hub):
        return dispatch_ready(self.plan, ledger, hub, self.router,
                              worker_for=lambda part: "local-worker")

    def check_unverified_receipt(self, response):
        hub = ReceiptHub(response)
        with TemporaryDirectory() as directory:
            database = str(Path(directory) / "retained.sqlite3")
            with Ledger(database) as ledger:
                report = self.dispatch(ledger, hub)
                self.assertEqual(report.started, ("later",))
                self.assertEqual(report.outcome_unknown, ("first",))
                self.assertEqual(report.not_ready, ("dependent",))
                first = ledger.part(self.plan.project_id, "first")
                self.assertEqual(first["state"], "outcome_unknown")
                self.assertIsNone(first["task_id"])
                self.assertEqual(first["evidence"], {
                    "source": "hub adapter",
                    "locator": self.plan.idempotency_key("first"),
                    "finding": "submit returned no verifiable task identifier",
                })
                self.assertEqual(
                    [event["event"] for event in ledger.events(self.plan.project_id, "first")],
                    ["dispatch_started", "outcome_unknown"],
                )
                saved = inspect_project(ledger, self.plan.project_id)
                events = ledger.events(self.plan.project_id)

            with Ledger(database) as ledger:
                # Retained data must remain inspectable and cannot cause a replay.
                self.assertEqual(inspect_project(ledger, self.plan.project_id), saved)
                replay = self.dispatch(ledger, hub)
                self.assertEqual(replay.started, ())
                self.assertEqual(replay.outcome_unknown, ())
                self.assertEqual(replay.not_ready, ("dependent",))
                self.assertEqual(ledger.events(self.plan.project_id), events)
                self.assertEqual(inspect_project(ledger, self.plan.project_id), saved)
                self.assertEqual(
                    [part["state"] for part in saved["parts"]],
                    ["outcome_unknown", "running", "queued"],
                )

            with Ledger.open_readonly(database) as ledger:
                self.assertEqual(inspect_project(ledger, self.plan.project_id), saved)
            self.assertEqual(hub.calls, [
                ("first", self.plan.idempotency_key("first")),
                ("later", self.plan.idempotency_key("later")),
            ])

    def test_json_decoded_lone_surrogates_remain_unknown_and_do_not_stop_dispatch(self):
        for escaped in (r"\ud800", r"\udfff", r"remote-\ud800-suffix",
                        r"\udc00\ud800"):
            with self.subTest(escaped=escaped):
                self.check_unverified_receipt(json.loads('{"task_id":"' + escaped + '"}'))

    def test_direct_python_surrogate_pairs_are_unstorable_receipts(self):
        # JSON decoders combine valid pairs; a raw Python string may still retain both units.
        self.check_unverified_receipt({"task_id": "remote-\ud83e\udded"})

    def test_existing_missing_blank_and_nonstring_receipts_keep_the_same_behavior(self):
        for response in ({}, {"task_id": None}, {"task_id": 17},
                         {"task_id": ""}, {"task_id": " \t\n"}, [], None):
            with self.subTest(response=response):
                self.check_unverified_receipt(response)

    def test_valid_unicode_identifiers_remain_exact_after_reopen_and_completion(self):
        identifiers = (
            "local-ascii",
            "  reçu-東京-🧭  ",
            json.loads(r'"remote-\ud83e\udded"'),
            "remote-\U00010000-\U0010ffff",
        )
        for task_id in identifiers:
            with self.subTest(task_id=task_id), TemporaryDirectory() as directory:
                database = str(Path(directory) / "retained.sqlite3")
                hub = ReceiptHub({"task_id": task_id})
                with Ledger(database) as ledger:
                    report = self.dispatch(ledger, hub)
                    self.assertEqual(report.started, ("first", "later"))
                    self.assertEqual(report.outcome_unknown, ())
                    self.assertEqual(report.not_ready, ("dependent",))
                    self.assertEqual(ledger.part(self.plan.project_id, "first")["task_id"], task_id)
                    self.assertEqual(
                        ledger.events(self.plan.project_id, "first")[-1]["detail"]["task_id"],
                        task_id,
                    )

                with Ledger(database) as ledger:
                    saved = inspect_project(ledger, self.plan.project_id)
                    self.assertEqual(saved["parts"][0]["task_id"], task_id)
                    self.assertEqual(self.dispatch(ledger, hub).started, ())
                    ledger.mark_completed(self.plan.project_id, "first", "local:artifact-first")
                    self.assertEqual(self.dispatch(ledger, hub).started, ("dependent",))
                    self.assertEqual(ledger.part(self.plan.project_id, "first")["task_id"], task_id)
                self.assertEqual([part_id for part_id, key in hub.calls],
                                 ["first", "later", "dependent"])

    def test_unrelated_response_values_are_not_reencoded_or_stored(self):
        response = {"task_id": "valid-task", "unused": "\ud800"}
        hub = ReceiptHub(response)
        with Ledger() as ledger:
            report = self.dispatch(ledger, hub)
            self.assertEqual(report.started, ("first", "later"))
            self.assertEqual(report.outcome_unknown, ())
            self.assertEqual(ledger.part(self.plan.project_id, "first")["task_id"], "valid-task")
        self.assertEqual(response, {"task_id": "valid-task", "unused": "\ud800"})


if __name__ == "__main__":
    unittest.main()
