"""Bind completed artifact text literally, without a subclass's SQLite adapter."""
from pathlib import Path
import tempfile
import unittest

from fanout_engine import Ledger, LedgerError, Plan, inspect_project


EVIDENCE = {"source": "local fixture", "locator": "fixture://artifact",
            "finding": "artifact bytes were verified"}


class ArtifactReferenceBindingTests(unittest.TestCase):
    def prepare(self, ledger, mode):
        ledger.record_plan(Plan.from_dict({"project": "artifact-binding", "parts": [
            {"id": "work", "instruction": "Retain the result."},
        ]}))
        ledger.mark_dispatching("artifact-binding", "work", "worker",
                                {"model": "local", "effort": "low"})
        if mode == "direct":
            ledger.mark_running("artifact-binding", "work", "task")
        else:
            ledger.mark_outcome_unknown("artifact-binding", "work", EVIDENCE)

    def complete(self, ledger, mode, reference):
        if mode == "direct":
            ledger.mark_completed("artifact-binding", "work", reference, EVIDENCE)
        else:
            ledger.reconcile_unknown("artifact-binding", "work", verdict="completed",
                                     artifact_ref=reference, evidence=EVIDENCE)

    def test_literal_subclass_reference_survives_both_completed_paths_and_reopen(self):
        for mode in ("direct", "reconciled"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                database = Path(directory) / "retained 東京.sqlite3"
                calls = []

                class Reference(str):
                    def __conform__(self, protocol):
                        calls.append("sqlite adaptation")
                        return "   "

                    def __bool__(self):
                        raise AssertionError("use literal text, not overridden truthiness")

                    def strip(self, *args, **kwargs):
                        raise AssertionError("use literal text, not overridden strip")

                    def encode(self, *args, **kwargs):
                        raise AssertionError("use literal text, not overridden encode")

                    def __str__(self):
                        raise AssertionError("use literal text, not overridden conversion")

                literal = "  artifact://résumé-東京-🧭  "
                reference = Reference(literal)
                with Ledger(str(database)) as ledger:
                    self.prepare(ledger, mode)
                    self.complete(ledger, mode, reference)
                before = database.read_bytes()
                with Ledger.open_readonly(database) as ledger:
                    row = ledger.part("artifact-binding", "work")
                    event = ledger.events("artifact-binding")[-1]
                    report = inspect_project(ledger, "artifact-binding")
                self.assertEqual(row["state"], "completed")
                self.assertEqual(row["artifact_ref"], literal)
                self.assertEqual(event["detail"]["artifact_ref"], literal)
                self.assertEqual(report["parts"][0]["artifact_ref"], literal)
                self.assertEqual(calls, [])
                self.assertEqual(database.read_bytes(), before)

    def test_invalid_literal_subclass_refuses_before_sql_or_state_changes(self):
        class Reference(str):
            def strip(self, *args, **kwargs):
                return "artifact://invented"

            def encode(self, *args, **kwargs):
                return b"artifact://invented"

            def __str__(self):
                raise AssertionError("invalid input must be refused before conversion")

            def __conform__(self, protocol):
                raise AssertionError("invalid input must be refused before SQLite binding")

        for mode in ("direct", "reconciled"):
            for literal in (" \t\u2003 ", "artifact://" + chr(0xD800)):
                with self.subTest(mode=mode, literal=repr(literal)), Ledger() as ledger:
                    self.prepare(ledger, mode)
                    before = ledger.part("artifact-binding", "work")
                    events = ledger.events("artifact-binding")
                    sql = []
                    ledger._db.set_trace_callback(sql.append)
                    try:
                        with self.assertRaises(LedgerError):
                            self.complete(ledger, mode, Reference(literal))
                    finally:
                        ledger._db.set_trace_callback(None)
                    self.assertEqual(sql, [])
                    self.assertEqual(ledger.part("artifact-binding", "work"), before)
                    self.assertEqual(ledger.events("artifact-binding"), events)


if __name__ == "__main__":
    unittest.main()
