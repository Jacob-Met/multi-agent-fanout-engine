"""Ledger admission must preserve the validated native plan identity."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from fanout_engine import EffortRouter, Ledger, Part, Plan, Route, dispatch_ready, inspect_project
from fanout_engine.ledger import LedgerError


class MutablePart:
    def __init__(self):
        self.id = "last"
        self.instruction = "Read both sources."
        self.depends_on = ["right", "left"]
        self.tags = ["zeta", "alpha", "zeta"]

    def to_dict(self):
        return {"id": self.id, "instruction": self.instruction,
                "depends_on": list(self.depends_on), "tags": list(self.tags)}


def authored_plan():
    source = MutablePart()
    plan = Plan("ledger-capture", (
        source, Part("left", "Read the left source."),
        Part("right", "Read the right source."),
    ))
    return source, plan


def valid_edits():
    return {
        "identifier": lambda part: setattr(part, "id", "renamed"),
        "instruction": lambda part: setattr(part, "instruction", "Changed after validation."),
        "dependencies": lambda part: part.depends_on.clear(),
        "repeated tags": lambda part: part.tags.pop(),
    }


class LocalHub:
    def __init__(self):
        self.calls = []

    def submit(self, part, **kwargs):
        self.calls.append((part, kwargs))
        return {"task_id": "local-test-only-" + part.id}


class LedgerPlanIdentityTests(unittest.TestCase):
    def test_unchanged_capture_reopens_with_exact_native_identity(self):
        source, plan = authored_plan()
        document = copy.deepcopy(plan.to_dict())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            with Ledger(str(path)) as ledger:
                self.assertTrue(ledger.record_plan(plan))
                events = ledger.events(plan.project_id)
                self.assertFalse(ledger.record_plan(plan))
                self.assertEqual(ledger.events(plan.project_id), events)
            with Ledger.open_readonly(path) as ledger:
                snapshot = ledger.project_snapshot(plan.project_id)
                self.assertEqual(json.loads(snapshot["plan_json"]), document)
                report = inspect_project(ledger, plan.project_id)
                self.assertEqual(report["plan_digest"], plan.digest)
                self.assertEqual([part["id"] for part in report["parts"]], ["last", "left", "right"])
                self.assertEqual(report["queued_ready_ids"], ["left", "right"])
                self.assertEqual(report["parts"][0]["tags"], ["zeta", "alpha", "zeta"])
                self.assertEqual(report["parts"][0]["depends_on"], ["right", "left"])
                for part in report["parts"]:
                    self.assertEqual(part["idempotency_key"], plan.idempotency_key(part["id"]))
        self.assertIs(plan.parts[0], source)
        self.assertEqual(plan.to_dict(), document)

    def test_edited_plan_is_refused_before_first_write_transaction(self):
        for label, edit in valid_edits().items():
            with self.subTest(edit=label), Ledger(":memory:") as ledger:
                source, plan = authored_plan()
                edit(source)
                statements = []
                ledger._db.set_trace_callback(statements.append)
                with self.assertRaisesRegex(LedgerError, "changed since validation"):
                    ledger.record_plan(plan)
                self.assertFalse(any(sql.lstrip().upper().startswith("BEGIN") for sql in statements))
                self.assertIsNone(ledger.project_snapshot(plan.project_id))
                self.assertEqual(ledger.events(plan.project_id), [])
                self.assertFalse(ledger._db.in_transaction)

    def test_edited_rerecord_preserves_the_retained_project_and_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.sqlite3"
            _, plan = authored_plan()
            with Ledger(str(path)) as ledger:
                ledger.record_plan(plan)
                before = inspect_project(ledger, plan.project_id)
                events = ledger.events(plan.project_id)
            original_bytes = path.read_bytes()
            with Ledger(str(path)) as ledger:
                for label, edit in valid_edits().items():
                    with self.subTest(edit=label):
                        source, stale = authored_plan()
                        edit(source)
                        with self.assertRaisesRegex(LedgerError, "changed since validation"):
                            ledger.record_plan(stale)
                        self.assertEqual(inspect_project(ledger, plan.project_id), before)
                        self.assertEqual(ledger.events(plan.project_id), events)
            self.assertEqual(path.read_bytes(), original_bytes)

    def test_invalid_changed_source_never_creates_a_project(self):
        for attribute, value in (
            ("instruction", " "), ("depends_on", ["absent"]), ("tags", ["not a tag"]),
        ):
            with self.subTest(attribute=attribute), Ledger(":memory:") as ledger:
                source, plan = authored_plan()
                setattr(source, attribute, value)
                with self.assertRaises(ValueError):
                    ledger.record_plan(plan)
                self.assertIsNone(ledger.project_snapshot(plan.project_id))
                self.assertEqual(ledger.events(plan.project_id), [])

    def test_edit_during_native_persistence_cannot_change_captured_part_rows(self):
        source, plan = authored_plan()
        document = copy.deepcopy(plan.to_dict())
        with Ledger(":memory:") as ledger:
            def edit_on_begin(statement):
                if statement.lstrip().upper().startswith("BEGIN"):
                    source.instruction = "Changed while the capture is being recorded."
                    source.depends_on.clear()
                    source.tags[:] = ["replacement"]

            ledger._db.set_trace_callback(edit_on_begin)
            self.assertTrue(ledger.record_plan(plan))
            ledger._db.set_trace_callback(None)
            self.assertNotEqual(plan.to_dict(), document)
            snapshot = ledger.project_snapshot(plan.project_id)
            self.assertEqual(json.loads(snapshot["plan_json"]), document)
            report = inspect_project(ledger, plan.project_id)
            self.assertEqual(report["parts"][0]["instruction"], document["parts"][0]["instruction"])
            self.assertEqual(report["parts"][0]["depends_on"], ["right", "left"])
            self.assertEqual(report["parts"][0]["tags"], ["zeta", "alpha", "zeta"])
            self.assertEqual(report["queued_ready_ids"], ["left", "right"])

    def test_stale_dispatch_entry_never_calls_worker_or_hub(self):
        for already_recorded in (False, True):
            with self.subTest(already_recorded=already_recorded), Ledger(":memory:") as ledger:
                source, plan = authored_plan()
                if already_recorded:
                    ledger.record_plan(plan)
                before = ledger.project_snapshot(plan.project_id)
                events = ledger.events(plan.project_id)
                source.instruction = "Changed blocked-part instruction."
                hub = LocalHub()
                workers = []
                router = EffortRouter({"local-model": ("low",)}, pool=(Route("local-model", "low"),))
                def worker_for(part):
                    workers.append(part.id)
                    return "local-test-only"

                with self.assertRaisesRegex(LedgerError, "changed since validation"):
                    dispatch_ready(plan, ledger, hub, router, worker_for=worker_for)
                self.assertEqual(workers, [])
                self.assertEqual(hub.calls, [])
                self.assertEqual(ledger.project_snapshot(plan.project_id), before)
                self.assertEqual(ledger.events(plan.project_id), events)


if __name__ == "__main__":
    unittest.main()
