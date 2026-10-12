"""Selected-project history stays bounded and retained ledgers remain readable."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from fanout_engine import EffortRouter, Ledger, Part, Plan, Route, dispatch_ready
from fanout_engine.history import inspect_history
from fanout_engine.inspection import inspect_project


FIXTURE = Path(__file__).parent / "fixtures/event_history_before_project_index.sql"


def retained_rows(database):
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    try:
        return {
            "projects": connection.execute("SELECT * FROM projects ORDER BY project_id").fetchall(),
            "parts": connection.execute("SELECT * FROM parts ORDER BY project_id,part_id").fetchall(),
            "events": connection.execute("SELECT * FROM events ORDER BY seq").fetchall(),
        }
    finally:
        connection.close()


def reports(ledger):
    return {project: (inspect_project(ledger, project), inspect_history(ledger, project))
            for project in ("legacy-project", "other-project")}


class HistoryLookupTests(unittest.TestCase):
    def test_legacy_writable_open_preserves_complete_records_and_no_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "retained.sqlite3"
            connection = sqlite3.connect(database)
            try:
                connection.executescript(FIXTURE.read_text(encoding="utf-8"))
            finally:
                connection.close()
            before_rows = retained_rows(database)
            original_bytes = database.read_bytes()
            with Ledger.open_readonly(database) as ledger:
                before = reports(ledger)
            self.assertEqual(database.read_bytes(), original_bytes)
            self.assertEqual([event["seq"] for event in before["legacy-project"][1]["events"]],
                             [1, 2, 3, 5, 6, 7, 8])
            self.assertEqual(before["legacy-project"][0]["parts"][0]["tags"], ["reading", "reading"])
            self.assertEqual(before["legacy-project"][0]["parts"][1]["task_id"], "accepted-α")

            document = json.loads(next(row[2] for row in before_rows["projects"]
                                       if row[0] == "legacy-project"))
            plan = Plan(document["project"], tuple(
                Part(part["id"], part["instruction"], tuple(part["depends_on"]), tuple(part["tags"]))
                for part in document["parts"]
            ))
            calls = []

            class LocalHub:
                def submit(self, part, **kwargs):
                    calls.append(part.id)
                    return {"task_id": "unexpected-new-work"}

            router = EffortRouter({"fixture-model": ("low",)}, pool=(Route("fixture-model", "low"),))
            with Ledger(str(database)) as ledger:
                self.assertEqual(reports(ledger), before)
                report = dispatch_ready(plan, ledger, LocalHub(), router,
                                        worker_for=lambda part: "unneeded-worker")
                self.assertEqual(report.started, ())
                self.assertEqual(report.outcome_unknown, ())
                self.assertEqual(report.not_ready, ("waiting",))
                self.assertEqual(calls, [])
                self.assertEqual(reports(ledger), before)
            self.assertEqual(retained_rows(database), before_rows)

            # Opening the upgraded file again is inert, including its byte identity.
            upgraded_bytes = database.read_bytes()
            with Ledger(str(database)) as ledger:
                self.assertEqual(reports(ledger), before)
            with Ledger.open_readonly(database) as ledger:
                self.assertEqual(reports(ledger), before)
            self.assertEqual(database.read_bytes(), upgraded_bytes)
            self.assertEqual(retained_rows(database), before_rows)

    def test_selected_history_work_does_not_scan_unrelated_projects(self):
        with Ledger() as ledger:
            def record(project):
                plan = Plan(project, (Part("one", "Retain authored work."),))
                ledger.record_plan(plan)
                ledger.mark_dispatching(project, "one", "fixture-worker",
                                        {"model": "fixture-model", "effort": "low"})
                ledger.mark_running(project, "one", "task-" + project)
                ledger.mark_outcome_unknown(project, "one", {
                    "source": "authored fixture", "locator": plan.idempotency_key("one"),
                    "finding": "No external work was submitted.",
                })

            def receive():
                steps = 0

                def count_step():
                    nonlocal steps
                    steps += 1
                    return 0

                ledger._db.set_progress_handler(count_step, 1)
                try:
                    result = inspect_history(ledger, "target")
                finally:
                    ledger._db.set_progress_handler(None, 0)
                return result, steps

            record("target")
            before, small_steps = receive()
            for index in range(256):
                record("neighbor-" + str(index))
            after, populated_steps = receive()
            self.assertEqual(after, before)
            self.assertEqual(len(after["events"]), 4)
            self.assertGreater(small_steps, 0)
            # A broad work bound tolerates planner/B-tree differences. It is not
            # a timing threshold or an assertion about a particular index name.
            self.assertLessEqual(populated_steps, small_steps * 2,
                                 "selected history scanned unrelated project events")


if __name__ == "__main__":
    unittest.main()
