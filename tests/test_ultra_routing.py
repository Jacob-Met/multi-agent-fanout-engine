import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import (
    EffortRouter, Ledger, Part, Plan, Route, UnsafeStepUp,
    dispatch_ready, inspect_project,
)

ROOT = Path(__file__).resolve().parents[1]


class UltraRoutingTests(unittest.TestCase):
    def test_authorized_ultra_pool_and_explicit_routes_retain_the_literal_effort(self):
        first = Route("model-a", "ultra")
        second = Route("model-b", "ultra")
        router = EffortRouter(
            {"model-a": ("ultra",), "model-b": ("ultra",)}, pool=(first,),
        )
        self.assertEqual(router.route_for("review"), first)
        self.assertEqual(router.route_for("review", second), second)
        self.assertEqual(router.route_for("review").effort, "ultra")

    def test_ultra_still_requires_authorization_for_that_model(self):
        ultra = Route("model-a", "ultra")
        with self.assertRaisesRegex(ValueError, "effort is not authorized"):
            EffortRouter({"model-a": ("high",)}, pool=(ultra,))
        levels = ["high"]
        router = EffortRouter({"model-a": levels}, pool=(Route("model-a", "high"),))
        levels.append("ultra")
        with self.assertRaisesRegex(ValueError, "effort is not authorized"):
            router.route_for("review", ultra)
        with self.assertRaisesRegex(ValueError, "not in the authorized catalog"):
            router.route_for("review", Route("model-b", "ultra"))

    def test_ultra_step_up_keeps_the_existing_refusal_boundary(self):
        current = Route("model-a", "high")
        stronger = Route("model-a", "ultra")
        router = EffortRouter(
            {"model-a": ("high", "ultra")}, pool=(current,), step_up=stronger,
        )
        self.assertEqual(router.step_up_after_refusal(
            current, refusal_before_output=True,
        ), stronger)
        for flags in (
            {"refusal_before_output": False},
            {"refusal_before_output": True, "output_received": True},
            {"refusal_before_output": True, "effect_started": True},
        ):
            with self.subTest(flags=flags), self.assertRaises(UnsafeStepUp):
                router.step_up_after_refusal(current, **flags)
        with self.assertRaises(UnsafeStepUp):
            router.step_up_after_refusal(stronger, refusal_before_output=True)

    def test_existing_efforts_and_exact_spelling_remain_unchanged(self):
        for effort in ("low", "medium", "high", "xhigh", "max"):
            with self.subTest(effort=effort):
                route = Route("model-a", effort)
                router = EffortRouter({"model-a": (effort,)}, pool=(route,))
                self.assertEqual(router.route_for("review"), route)
        for effort in ("Ultra", "ULTRA", " ultra", "ultra ", "turbo", ""):
            with self.subTest(effort=effort), self.assertRaises(ValueError):
                Route("model-a", effort)

    def test_preview_cli_saves_ultra_metadata_and_refuses_an_unauthorized_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            plan_path = directory / "authored plan.json"
            routes_path = directory / "authorized routes.json"
            output = directory / "review output.json"
            plan = Plan("ultra-preview", (Part("review", "Review supplied material."),))
            plan_path.write_text(json.dumps(plan.to_dict()), encoding="utf-8")
            routes = {
                "catalog": {"model-a": ["ultra"]},
                "pool": [{"model": "model-a", "effort": "ultra"}],
                "step_up": {"model": "model-a", "effort": "ultra"},
            }
            routes_path.write_text(json.dumps(routes), encoding="utf-8")
            command = [sys.executable, "-B", "-m", "fanout_engine.preview",
                       "--plan", str(plan_path), "--routes", str(routes_path)]
            result = subprocess.run(command + ["--output", str(output)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["routes"][0]["route"], routes["pool"][0])
            self.assertEqual(report["configured_step_up"], routes["step_up"])
            self.assertEqual(report["plan_digest"], plan.digest)
            self.assertEqual(report["routes"][0]["idempotency_key"],
                             plan.idempotency_key("review"))

            routes["catalog"]["model-a"] = ["high"]
            routes_path.write_text(json.dumps(routes), encoding="utf-8")
            denied_output = directory / "must remain absent.json"
            denied = subprocess.run(command + ["--output", str(denied_output)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(denied.returncode, 2)
            self.assertIn("effort is not authorized", denied.stderr)
            self.assertEqual(denied.stdout, "")
            self.assertFalse(denied_output.exists())

    def test_dispatch_retains_ultra_in_sqlite_without_replaying_an_unknown_submit(self):
        class RecordingHub:
            def __init__(self):
                self.calls = []

            def submit(self, part, *, route, worker_id, idempotency_key):
                self.calls.append((part.id, route, idempotency_key))
                if part.id == "uncertain":
                    raise TimeoutError("synthetic lost reply")
                return {"task_id": "task-" + part.id}

        plan = Plan("ultra-dispatch", (
            Part("accepted", "Review one source."),
            Part("uncertain", "Review the other source."),
        ))
        route = Route("model-a", "ultra")
        router = EffortRouter({"model-a": ("ultra",)}, pool=(route,))
        hub = RecordingHub()
        with tempfile.TemporaryDirectory() as temporary:
            database = str(Path(temporary) / "retained.sqlite3")
            with Ledger(database) as ledger:
                result = dispatch_ready(plan, ledger, hub, router, worker_for=lambda _: "worker-a")
                self.assertEqual(result.started, ("accepted",))
                self.assertEqual(result.outcome_unknown, ("uncertain",))
            with Ledger.open_readonly(database) as ledger:
                report = inspect_project(ledger, plan.project_id)
                self.assertEqual([part["state"] for part in report["parts"]],
                                 ["running", "outcome_unknown"])
                for part in report["parts"]:
                    self.assertEqual(part["route"], {"model": "model-a", "effort": "ultra"})
                    self.assertEqual(part["idempotency_key"], plan.idempotency_key(part["id"]))
            with Ledger(database) as ledger:
                repeated = dispatch_ready(plan, ledger, hub, router, worker_for=lambda _: "worker-a")
                self.assertEqual(repeated.started, ())
                self.assertEqual(repeated.outcome_unknown, ())
            self.assertEqual(len(hub.calls), 2)
            self.assertTrue(all(call[1] == route for call in hub.calls))


if __name__ == "__main__":
    unittest.main()
