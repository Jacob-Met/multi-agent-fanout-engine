import copy
import json
import sqlite3
import sys
import unittest

from fanout_engine import InspectionError, Ledger, Part, Plan, inspect_project


def mixed_plan():
    return Plan.from_dict({
        "project": "review-example",
        "parts": [
            {"id": "research", "instruction": "Read authored sample references."},
            {"id": "draft", "instruction": "Prepare authored text."},
            {"id": "fetch", "instruction": "Retrieve the local fixture material."},
            {"id": "verify", "instruction": "Check retrieved material.", "depends_on": ["fetch"]},
            {"id": "benchmark", "instruction": "Evaluate the authored control."},
            {"id": "signoff", "instruction": "Review evaluation.", "depends_on": ["benchmark"]},
            {"id": "publish", "instruction": "Prepare a local review artifact.",
             "depends_on": ["draft", "verify", "signoff"]},
            {"id": "notes", "instruction": "Prepare fixture notes."},
        ],
    })


def populate_mixed(ledger):
    plan = mixed_plan()
    ledger.record_plan(plan)
    for name in ("research", "draft", "fetch", "benchmark"):
        ledger.mark_dispatching(plan.project_id, name, "authored-worker",
                                {"model": "model-a", "effort": "low"})
        ledger.mark_running(plan.project_id, name, "authored-task-" + name)
    ledger.mark_completed(plan.project_id, "research", "authored-artifact:references")
    evidence = {"source": "authored local fixture", "locator": "fixture:fetch",
                "finding": "acceptance intentionally unverified in this example"}
    ledger.mark_outcome_unknown(plan.project_id, "fetch", evidence)
    ledger.mark_outcome_unknown(plan.project_id, "benchmark",
                                {**evidence, "locator": "fixture:benchmark"})
    ledger.reconcile_unknown(
        plan.project_id, "benchmark", verdict="failed",
        evidence={**evidence, "locator": "fixture:benchmark",
                  "finding": "authored failure control"},
    )
    return plan


class InspectionTests(unittest.TestCase):
    def receive(self, ledger, project_id, error_code=None):
        """Exercise the public consumer with writes denied and native rows compared."""
        before = list(ledger._db.iterdump())
        statements = []
        denied = []
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}

        def authorize(action, first, second, database, trigger):
            if action in allowed:
                return sqlite3.SQLITE_OK
            denied.append((action, first, second))
            return sqlite3.SQLITE_DENY

        ledger._db.set_trace_callback(statements.append)
        ledger._db.set_authorizer(authorize)
        try:
            if error_code is None:
                result = inspect_project(ledger, project_id)
            else:
                with self.assertRaises(InspectionError) as caught:
                    inspect_project(ledger, project_id)
                self.assertEqual(caught.exception.code, error_code)
                result = caught.exception
        finally:
            # Python 3.10 requires a callable; None only disables it on 3.11+.
            ledger._db.set_authorizer(lambda *_: sqlite3.SQLITE_OK)
            ledger._db.set_trace_callback(None)
        self.assertEqual(denied, [])
        self.assertEqual(len(statements), 1, statements)
        self.assertTrue(statements[0].lstrip().upper().startswith("SELECT"))
        self.assertEqual(list(ledger._db.iterdump()), before)
        return result

    def test_complete_mixed_project_and_direct_blockers(self):
        with Ledger() as ledger:
            plan = populate_mixed(ledger)
            report = self.receive(ledger, plan.project_id)
            self.assertEqual(report["project_id"], plan.project_id)
            self.assertEqual(report["plan_digest"], plan.digest)
            self.assertEqual([row["id"] for row in report["parts"]],
                             [part.id for part in plan.parts])
            self.assertEqual(report["queued_ready_ids"], ["notes"])
            self.assertEqual(report["blocked_queued_ids"], ["verify", "signoff", "publish"])
            self.assertEqual(report["state_counts"], {
                "queued": 4, "dispatching": 0, "running": 1,
                "outcome_unknown": 1, "completed": 1, "failed": 1,
            })
            rows = {row["id"]: row for row in report["parts"]}
            self.assertEqual(rows["verify"]["unmet_dependencies"],
                             [{"id": "fetch", "state": "outcome_unknown"}])
            self.assertEqual(rows["signoff"]["unmet_dependencies"],
                             [{"id": "benchmark", "state": "failed"}])
            self.assertEqual(rows["publish"]["unmet_dependencies"], [
                {"id": "draft", "state": "running"},
                {"id": "verify", "state": "queued"},
                {"id": "signoff", "state": "queued"},
            ])
            for part in plan.parts:
                native = ledger.part(plan.project_id, part.id)
                row = rows[part.id]
                for key, value in part.to_dict().items():
                    self.assertEqual(row[key], value)
                for key in ("state", "idempotency_key", "worker_id", "task_id",
                            "artifact_ref", "updated_at"):
                    self.assertEqual(row[key], native[key])
                self.assertEqual(row["route"], native.get("route"))
                self.assertEqual(row["evidence"], native.get("evidence"))
            self.assertEqual(len(ledger.events(plan.project_id)), 13)
            json.dumps(report, ensure_ascii=False, allow_nan=False).encode("utf-8")

    def test_direct_constructor_tags_and_dependency_order_remain_exact(self):
        plan = Plan("native-order", (
            Part("z", "First original item.", tags=("zeta", "alpha", "zeta")),
            Part("a", "Second original item."),
            Part("last", "Literal <tag> 東京\nquoted \"text\".",
                 depends_on=("z", "a"), tags=("second", "first")),
        ))
        self.assertNotEqual(Plan.from_dict(plan.to_dict()).digest, plan.digest)
        with Ledger() as ledger:
            ledger.record_plan(plan)
            report = self.receive(ledger, plan.project_id)
            self.assertEqual(report["plan_digest"], plan.digest)
            self.assertEqual([row["id"] for row in report["parts"]], ["z", "a", "last"])
            self.assertEqual(report["parts"][0]["tags"], ["zeta", "alpha", "zeta"])
            self.assertEqual(report["parts"][2]["depends_on"], ["z", "a"])
            self.assertEqual(report["parts"][2]["unmet_dependencies"],
                             [{"id": "z", "state": "queued"}, {"id": "a", "state": "queued"}])
            self.assertEqual(report["queued_ready_ids"], ["z", "a"])

    def test_detached_snapshots_and_later_native_progress(self):
        with Ledger() as ledger:
            plan = populate_mixed(ledger)
            first = self.receive(ledger, plan.project_id)
            original = copy.deepcopy(first)
            first["parts"][2]["evidence"]["finding"] = "caller edit"
            first["parts"][6]["depends_on"].clear()
            first["parts"][6]["unmet_dependencies"][0]["state"] = "completed"
            first["state_counts"]["running"] = 900
            first["queued_ready_ids"].clear()
            raw = ledger.project_snapshot(plan.project_id)
            raw["parts"][0]["state"] = "caller edit"
            raw["plan_json"] = "{}"
            self.assertEqual(self.receive(ledger, plan.project_id), original)
            ledger.mark_completed(plan.project_id, "draft", "authored-artifact:draft")
            later = self.receive(ledger, plan.project_id)
            self.assertEqual(later["parts"][1]["state"], "completed")
            self.assertEqual(later["parts"][6]["unmet_dependencies"], [
                {"id": "verify", "state": "queued"},
                {"id": "signoff", "state": "queued"},
            ])
            self.assertEqual(original["parts"][1]["state"], "running")

    def test_all_six_states_are_observed_without_recovery_or_reclassification(self):
        states = ("queued", "dispatching", "running", "outcome_unknown", "completed", "failed")
        plan = Plan("all-states", tuple(Part(name, "Authored " + name) for name in states))
        with Ledger() as ledger:
            ledger.record_plan(plan)
            for name in states[1:]:
                ledger.mark_dispatching(plan.project_id, name, "worker", {"opaque": ["kept"]})
                if name != "dispatching":
                    ledger.mark_running(plan.project_id, name, "task-" + name)
            proof = {"source": "fixture", "locator": "fixture:unknown", "finding": "unknown"}
            ledger.mark_outcome_unknown(plan.project_id, "outcome_unknown", proof)
            ledger.mark_completed(plan.project_id, "completed", "artifact:complete")
            ledger.mark_outcome_unknown(plan.project_id, "failed", proof)
            ledger.reconcile_unknown(plan.project_id, "failed", verdict="failed", evidence=proof)
            report = self.receive(ledger, plan.project_id)
            self.assertEqual([row["state"] for row in report["parts"]], list(states))
            self.assertEqual(report["state_counts"], dict.fromkeys(states, 1))
            self.assertEqual(report["queued_ready_ids"], ["queued"])
            self.assertEqual(report["blocked_queued_ids"], [])
            self.assertIsNone(report["parts"][1]["task_id"])
            self.assertEqual(report["parts"][1]["state"], "dispatching")

    def test_unknown_project_and_missing_parts_are_distinct(self):
        with Ledger() as ledger:
            self.receive(ledger, "absent", "project_not_found")
            plan = populate_mixed(ledger)
            ledger._db.execute("DELETE FROM parts WHERE project_id=? AND part_id='fetch'",
                               (plan.project_id,))
            error = self.receive(ledger, plan.project_id, "missing_parts")
            self.assertIn("fetch", str(error))
            ledger._db.execute("DELETE FROM parts WHERE project_id=?", (plan.project_id,))
            self.receive(ledger, plan.project_id, "missing_parts")

    def test_malformed_or_changed_stored_plan_refuses_without_partial_report(self):
        updates = [
            ("plan_json", "{"),
            ("plan_json", '{"project":"a","project":"b","parts":[]}'),
            ("plan_json", '{"project":"wrong","parts":[]}'),
            ("plan_digest", "different"),
        ]
        for column, value in updates:
            with self.subTest(column=column, value=value), Ledger() as ledger:
                plan = populate_mixed(ledger)
                ledger._db.execute("UPDATE projects SET " + column + "=? WHERE project_id=?",
                                   (value, plan.project_id))
                self.receive(ledger, plan.project_id, "invalid_record")

    def test_malformed_or_inconsistent_part_rows_refuse_without_write(self):
        updates = [
            ("payload_json", "{"),
            ("payload_json", '{"id":"notes","instruction":"Changed","depends_on":[],"tags":[]}'),
            ("payload_digest", "different"),
            ("idempotency_key", "different"),
            ("route_json", '{"duplicate":1,"duplicate":2}'),
            ("evidence_json", '{"number":1e999}'),
            ("worker_id", sqlite3.Binary(b"not text")),
            ("updated_at", "not a timestamp"),
            ("updated_at", float("inf")),
        ]
        for column, value in updates:
            with self.subTest(column=column, value=str(value)), Ledger() as ledger:
                plan = populate_mixed(ledger)
                ledger._db.execute("UPDATE parts SET " + column
                                   + "=? WHERE project_id=? AND part_id='notes'",
                                   (value, plan.project_id))
                self.receive(ledger, plan.project_id, "invalid_record")
        with Ledger() as ledger:
            plan = populate_mixed(ledger)
            ledger._db.execute(
                "INSERT INTO parts SELECT project_id,'extra',payload_json,payload_digest,"
                "idempotency_key,state,worker_id,task_id,route_json,artifact_ref,evidence_json,updated_at "
                "FROM parts WHERE project_id=? AND part_id='notes'", (plan.project_id,))
            self.receive(ledger, plan.project_id, "invalid_record")
        with Ledger() as ledger:
            plan = populate_mixed(ledger)
            ledger._db.execute("PRAGMA ignore_check_constraints=ON")
            ledger._db.execute("UPDATE parts SET state='unrecognized' WHERE part_id='notes'")
            self.receive(ledger, plan.project_id, "invalid_record")

    def test_configured_integer_conversion_limit_has_the_public_refusal_code(self):
        limit = getattr(sys, "get_int_max_str_digits", lambda: 0)()
        if limit == 0:
            self.skipTest("this interpreter has no active integer conversion limit")
        stored = '{"stored_integer":' + "9" * (limit + 1) + "}"
        for column in ("route_json", "evidence_json"):
            with self.subTest(column=column), Ledger() as ledger:
                plan = populate_mixed(ledger)
                ledger._db.execute("UPDATE parts SET " + column
                                   + "=? WHERE project_id=? AND part_id='notes'",
                                   (stored, plan.project_id))
                error = self.receive(ledger, plan.project_id, "invalid_record")
                self.assertIsInstance(error.__cause__, ValueError)

    def test_native_references_and_additional_evidence_are_preserved_as_data(self):
        plan = Plan("opaque-data", (Part("sample", "Keep literal text."),))
        route = {"model": "recorded-only model", "effort": "legacy value", "extra": ["東京", None]}
        evidence = {"source": "authored fixture", "locator": "opaque://not-opened/<tag>",
                    "finding": 'Original "finding"\nwith Unicode Ω',
                    "extra": {"values": [True, 0, None, {"literal": "<script>"}]}}
        with Ledger() as ledger:
            ledger.record_plan(plan)
            ledger.mark_dispatching(plan.project_id, "sample", "worker Ω", route)
            ledger.mark_running(plan.project_id, "sample", "task <tag>")
            ledger.mark_completed(plan.project_id, "sample", "artifact://not-opened/東京", evidence)
            report = self.receive(ledger, plan.project_id)
            row = report["parts"][0]
            self.assertEqual(row["route"], route)
            self.assertEqual(row["evidence"], evidence)
            self.assertEqual(row["worker_id"], "worker Ω")
            self.assertEqual(row["task_id"], "task <tag>")
            self.assertEqual(row["artifact_ref"], "artifact://not-opened/東京")
            self.assertEqual(report["queued_ready_ids"], [])
            json.dumps(report, ensure_ascii=False, allow_nan=False).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
