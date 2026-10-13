"""Literal evidence fields are admitted before any ledger transition."""
from contextlib import contextmanager
from pathlib import Path
import tempfile
import unittest

from fanout_engine import Ledger, LedgerError, Part, Plan, inspect_project
from fanout_engine.plan import canonical_json


FIELDS = ("source", "locator", "finding")
COURSES = ("unknown", "completed", "failed", "reconciled-completed", "reconciled-failed")
PROOF = {"source": "local review", "locator": "fixture://proof", "finding": "observed result"}


class EvidenceTextTests(unittest.TestCase):
    @contextmanager
    def ledger_for(self, course, database=":memory:"):
        with Ledger(str(database)) as ledger:
            ledger.record_plan(Plan("evidence", (Part("work", "Retain evidence"),)))
            ledger.mark_dispatching("evidence", "work", "local-worker",
                                    {"model": "local-model", "effort": "low"})
            ledger.mark_running("evidence", "work", "local-task")
            if course.startswith("reconciled-"):
                ledger.mark_outcome_unknown("evidence", "work", PROOF)
            yield ledger

    def transition(self, ledger, course, evidence):
        if course == "unknown":
            ledger.mark_outcome_unknown("evidence", "work", evidence)
        elif course == "completed":
            ledger.mark_completed("evidence", "work", "fixture://artifact", evidence)
        elif course == "failed":
            ledger.mark_failed("evidence", "work", evidence)
        else:
            verdict = course.removeprefix("reconciled-")
            ledger.reconcile_unknown("evidence", "work", verdict=verdict,
                                     evidence=evidence,
                                     artifact_ref="fixture://artifact" if verdict == "completed" else None)

    def rejected_without_transaction(self, course, evidence):
        with self.ledger_for(course) as ledger:
            before = ledger.project_snapshot("evidence")
            events = ledger.events("evidence")
            statements = []
            ledger._db.set_trace_callback(statements.append)
            try:
                with self.assertRaises(LedgerError):
                    self.transition(ledger, course, evidence)
                self.assertEqual(statements, [], "invalid evidence entered the database")
            finally:
                ledger._db.set_trace_callback(None)
            self.assertEqual(ledger.project_snapshot("evidence"), before)
            self.assertEqual(ledger.events("evidence"), events)

    def test_blank_literal_cannot_be_accepted_by_overridden_strip(self):
        calls = []

        class InventedText(str):
            def strip(self, *args, **kwargs):
                calls.append("strip")
                return "invented evidence"

        for course in COURSES:
            for field in FIELDS:
                for literal in (" \t\n", "\u00a0\u2003"):
                    with self.subTest(course=course, field=field, literal=repr(literal)):
                        evidence = {**PROOF, field: InventedText(literal)}
                        self.rejected_without_transaction(course, evidence)
        self.assertEqual(calls, [])

    def test_valid_literal_does_not_call_text_overrides(self):
        calls = []

        class HiddenText(str):
            def strip(self, *args, **kwargs):
                calls.append("hidden strip")
                return ""

        class RaisingText(str):
            def strip(self, *args, **kwargs):
                calls.append("raising strip")
                raise ValueError("authored text override")

            def encode(self, *args, **kwargs):
                calls.append("encode")
                raise ValueError("authored encoding override")

            def __str__(self):
                calls.append("str")
                return "substituted evidence"

            def __bool__(self):
                calls.append("bool")
                return False

        literal = "  reçu-東京-🧭 e\u0301\t"
        for course in COURSES:
            for kind in (HiddenText, RaisingText):
                with self.subTest(course=course, kind=kind.__name__):
                    evidence = {key: kind(literal) for key in FIELDS}
                    with self.ledger_for(course) as ledger:
                        self.transition(ledger, course, evidence)
                        expected = {key: literal for key in FIELDS}
                        self.assertEqual(ledger.part("evidence", "work")["evidence"], expected)
                        detail = ledger.events("evidence", "work")[-1]["detail"]
                        if course not in ("unknown", "failed"):
                            detail = detail["evidence"]
                        self.assertEqual(detail, expected)
        self.assertEqual(calls, [])

    def test_malformed_utf8_is_a_ledger_error_before_any_transaction(self):
        for course in COURSES:
            for field in FIELDS:
                for literal in ("\ud800", "\udfff"):
                    with self.subTest(course=course, field=field, literal=repr(literal)):
                        self.rejected_without_transaction(course, {**PROOF, field: literal})

    def test_existing_missing_nontext_and_blank_refusals_remain(self):
        for course in COURSES:
            for evidence in (None, [], {}, {"source": "review"}):
                if evidence is None and course == "completed":
                    continue  # Direct completion deliberately permits omitted evidence.
                with self.subTest(course=course, evidence=evidence):
                    self.rejected_without_transaction(course, evidence)
            for field in FIELDS:
                for value in ("", " \t", 1, b"evidence", None):
                    with self.subTest(course=course, field=field, value=value):
                        self.rejected_without_transaction(course, {**PROOF, field: value})

    def test_unicode_padding_and_additional_json_survive_retained_reopen(self):
        expected = {"source": "  local-東京  ", "locator": "\tfixture://résumé/🧭\n",
                    "finding": "  observed e\u0301  ", "detail": {"attempt": 1, "reviewed": True}}
        for course in COURSES:
            with self.subTest(course=course), tempfile.TemporaryDirectory() as folder:
                database = Path(folder) / "retained evidence.sqlite3"
                supplied = {**expected, "detail": dict(expected["detail"])}
                with self.ledger_for(course, database) as ledger:
                    before_count = len(ledger.events("evidence"))
                    self.transition(ledger, course, supplied)
                    self.assertEqual(len(ledger.events("evidence")), before_count + 1)
                    row = ledger.part("evidence", "work")
                    self.assertEqual(row["evidence"], expected)
                    self.assertEqual(row["evidence_json"], canonical_json(expected))
                    supplied["finding"] = "changed after recording"
                    supplied["detail"]["attempt"] = 2
                    snapshot = inspect_project(ledger, "evidence")
                    events = ledger.events("evidence")
                before = database.read_bytes()
                with Ledger.open_readonly(database) as reader:
                    self.assertEqual(inspect_project(reader, "evidence"), snapshot)
                    self.assertEqual(reader.events("evidence"), events)
                    self.assertEqual(reader.part("evidence", "work")["evidence"], expected)
                self.assertEqual(database.read_bytes(), before)

    def test_direct_completion_still_allows_omitted_optional_evidence(self):
        with self.ledger_for("completed") as ledger:
            ledger.mark_completed("evidence", "work", "fixture://artifact")
            self.assertEqual(ledger.part("evidence", "work")["state"], "completed")
            self.assertIsNone(ledger.part("evidence", "work")["evidence_json"])


if __name__ == "__main__":
    unittest.main()
