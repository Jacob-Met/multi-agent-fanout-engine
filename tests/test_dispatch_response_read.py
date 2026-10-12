"""Response-read failures retain uncertainty and do not strand independent work."""
from collections.abc import Mapping
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready, inspect_project


class DeferredResponse(Mapping):
    def __init__(self, value=None, error=None):
        self.value = value
        self.error = error

    def __getitem__(self, key):
        if key != "task_id":
            raise KeyError(key)
        if self.error is not None:
            raise self.error
        return self.value

    def __iter__(self):
        return iter(("task_id",))

    def __len__(self):
        return 1


class LocalHub:
    def __init__(self, first_response):
        self.first_response = first_response
        self.calls = []

    def submit(self, part, **options):
        self.calls.append((part.id, options["idempotency_key"]))
        if part.id == "first":
            return self.first_response
        return {"task_id": "local-" + part.id}


class DispatchResponseReadTests(unittest.TestCase):
    def setUp(self):
        self.plan = Plan.from_dict({"project": "response-read", "parts": [
            {"id": "first", "instruction": "First local task"},
            {"id": "second", "instruction": "Independent local task"},
            {"id": "dependent", "instruction": "Wait for first", "depends_on": ["first"]},
        ]})
        self.router = EffortRouter(
            {"local-model": ["low"]}, pool=[Route("local-model", "low")],
        )

    def dispatch(self, ledger, hub):
        return dispatch_ready(
            self.plan, ledger, hub, self.router, worker_for=lambda part: "local-worker",
        )

    def test_deferred_read_failure_is_durable_and_never_replayed(self):
        hub = LocalHub(DeferredResponse(error=OSError("private adapter detail")))
        with tempfile.TemporaryDirectory() as temporary:
            database = str(Path(temporary) / "dispatch.sqlite3")
            with Ledger(database) as ledger:
                report = self.dispatch(ledger, hub)
                self.assertEqual(report.started, ("second",))
                self.assertEqual(report.outcome_unknown, ("first",))
                self.assertEqual(report.not_ready, ("dependent",))
                row = ledger.part(self.plan.project_id, "first")
                self.assertEqual(row["state"], "outcome_unknown")
                self.assertIsNone(row["task_id"])
                self.assertEqual(row["payload"], self.plan.parts[0].to_dict())
                self.assertEqual(row["idempotency_key"], self.plan.idempotency_key("first"))
                self.assertEqual(row["evidence"], {
                    "source": "hub adapter",
                    "locator": self.plan.idempotency_key("first"),
                    "finding": "submit response raised OSError; remote acceptance is unverified",
                })
                self.assertNotIn("private adapter detail", str(ledger.events(self.plan.project_id)))
                self.assertEqual(
                    [event["event"] for event in ledger.events(self.plan.project_id, "first")],
                    ["dispatch_started", "outcome_unknown"],
                )
            with Ledger(database) as ledger:
                self.assertEqual(ledger.part(self.plan.project_id, "first"), row)
                inspection = inspect_project(ledger, self.plan.project_id)
                self.assertEqual(inspection["queued_ready_ids"], [])
                self.assertEqual(inspection["blocked_queued_ids"], ["dependent"])
                again = self.dispatch(ledger, hub)
                self.assertEqual(again.started, ())
                self.assertEqual(again.outcome_unknown, ())
                self.assertEqual(again.not_ready, ("dependent",))
                self.assertEqual([part for part, _ in hub.calls], ["first", "second"])
                ledger.reconcile_unknown(
                    self.plan.project_id, "first", verdict="completed", artifact_ref="local:result",
                    evidence={"source": "local fixture", "locator": "local:receipt", "finding": "completed"},
                )
                followup = self.dispatch(ledger, hub)
                self.assertEqual(followup.started, ("dependent",))
                self.assertEqual([part for part, _ in hub.calls], ["first", "second", "dependent"])
                self.assertEqual(
                    [key for part, key in hub.calls],
                    [self.plan.idempotency_key(part) for part, _ in hub.calls],
                )

    def test_ordinary_mapping_task_id_is_preserved_exactly(self):
        hub = LocalHub(DeferredResponse(value="  local-task-id  "))
        with Ledger() as ledger:
            report = self.dispatch(ledger, hub)
            self.assertEqual(report.started, ("first", "second"))
            self.assertEqual(report.outcome_unknown, ())
            self.assertEqual(ledger.part(self.plan.project_id, "first")["task_id"], "  local-task-id  ")

    def test_custom_get_errors_use_unknown_state(self):
        class BrokenGet(dict):
            def __init__(self, error):
                self.error = error

            def get(self, key, default=None):
                raise self.error("private deferred read detail")

        for error in (RuntimeError, ValueError):
            with self.subTest(error=error.__name__), Ledger() as ledger:
                report = self.dispatch(ledger, LocalHub(BrokenGet(error)))
                self.assertEqual(report.started, ("second",))
                self.assertEqual(report.outcome_unknown, ("first",))
                self.assertEqual(
                    ledger.part(self.plan.project_id, "first")["evidence"]["finding"],
                    f"submit response raised {error.__name__}; remote acceptance is unverified",
                )

    def test_missing_and_malformed_task_ids_keep_existing_finding(self):
        responses = [{}, {"task_id": ""}, {"task_id": " \t "}, {"task_id": None}, {"task_id": 7}, [], None]
        for response in responses:
            with self.subTest(response=response), Ledger() as ledger:
                report = self.dispatch(ledger, LocalHub(response))
                self.assertEqual(report.started, ("second",))
                self.assertEqual(report.outcome_unknown, ("first",))
                self.assertEqual(
                    ledger.part(self.plan.project_id, "first")["evidence"]["finding"],
                    "submit returned no verifiable task identifier",
                )

    def test_cancellation_propagates_and_existing_recovery_still_parks_it(self):
        for exception in (KeyboardInterrupt, SystemExit, GeneratorExit):
            with self.subTest(exception=exception.__name__), Ledger() as ledger:
                interruption = exception("stop local fixture")
                hub = LocalHub(DeferredResponse(error=interruption))
                with self.assertRaises(exception) as caught:
                    self.dispatch(ledger, hub)
                self.assertIs(caught.exception, interruption)
                self.assertEqual(ledger.part_state(self.plan.project_id, "first"), "dispatching")
                self.assertEqual(ledger.part_state(self.plan.project_id, "second"), "queued")
                self.assertEqual(ledger.mark_interrupted_dispatches_unknown(self.plan.project_id), 1)
                report = self.dispatch(ledger, hub)
                self.assertEqual(report.started, ("second",))
                self.assertEqual([part for part, _ in hub.calls], ["first", "second"])

    def test_unknown_recording_failure_is_not_suppressed(self):
        class UnwritableLedger(Ledger):
            def mark_outcome_unknown(self, *args, **kwargs):
                raise sqlite3.OperationalError("injected local persistence failure")

        hub = LocalHub(DeferredResponse(error=OSError("unreadable")))
        with UnwritableLedger() as ledger:
            with self.assertRaisesRegex(sqlite3.OperationalError, "injected local persistence failure"):
                self.dispatch(ledger, hub)
            self.assertEqual(ledger.part_state(self.plan.project_id, "first"), "dispatching")
            self.assertEqual(ledger.part_state(self.plan.project_id, "second"), "queued")
            self.assertEqual([part for part, _ in hub.calls], ["first"])


if __name__ == "__main__":
    unittest.main()
