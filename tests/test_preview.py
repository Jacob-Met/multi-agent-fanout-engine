import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import EffortRouter, Part, Plan, Route
from fanout_engine.preview import (
    MAX_PLAN_BYTES,
    MAX_REPORT_BYTES,
    MAX_ROUTING_BYTES,
    PreviewError,
    preview_plan,
)

ROOT = Path(__file__).resolve().parents[1]


def encoded(value):
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def snapshot(path):
    data = path.read_bytes()
    metadata = path.stat()
    return (data, metadata.st_ino, metadata.st_mtime_ns)


class PreviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fanout-preview-tests-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.plan_path = self.directory / "authored.json"
        self.routing_path = self.directory / "routing.json"
        self.plan_document = {
            "project": "preview-project",
            "parts": [
                {
                    "id": "draft", "instruction": "Write the draft.",
                    "depends_on": ["research"], "tags": ["z-tag", "a-tag", "z-tag"],
                },
                {"id": "research", "instruction": "Read the 日本語 source."},
                {"id": "notes", "instruction": "Prepare separate notes."},
                {
                    "id": "finish", "instruction": "Review both outputs.",
                    "depends_on": ["draft", "notes"],
                },
            ],
        }
        self.routing_document = {
            "catalog": {"model-a": ["low", "high"], "model-b": ["low", "high"]},
            "pool": [
                {"model": "model-a", "effort": "low"},
                {"model": "model-b", "effort": "low"},
            ],
            "explicit_routes": {"finish": {"model": "model-b", "effort": "high"}},
            "step_up": {"model": "model-b", "effort": "high"},
        }
        self.write_inputs()

    def write_inputs(self, plan=None, routing=None):
        plan = self.plan_document if plan is None else plan
        routing = self.routing_document if routing is None else routing
        self.plan_path.write_bytes(plan if isinstance(plan, bytes) else encoded(plan))
        self.routing_path.write_bytes(routing if isinstance(routing, bytes) else encoded(routing))

    def run_preview(self, output=None, *, audit=False, stdout=subprocess.PIPE, preexec_fn=None):
        before = {p: snapshot(p) for p in (self.plan_path, self.routing_path)}
        arguments = ["--plan", str(self.plan_path), "--routes", str(self.routing_path)]
        if output is not None:
            arguments += ["--output", str(output)]
        if audit:
            program = (
                "import runpy,sys\n"
                "def forbid(event,args):\n"
                " if event.startswith(('sqlite3.connect','socket.','subprocess.Popen')):\n"
                "  raise RuntimeError('preview attempted a forbidden operation: '+event)\n"
                "sys.addaudithook(forbid)\n"
                "sys.argv=['fanout_engine.preview',*sys.argv[1:]]\n"
                "runpy.run_module('fanout_engine.preview',run_name='__main__')\n"
            )
            command = [sys.executable, "-B", "-c", program, *arguments]
        else:
            command = [sys.executable, "-B", "-m", "fanout_engine.preview", *arguments]
        process = subprocess.run(
            command, cwd=ROOT, stdout=stdout, stderr=subprocess.PIPE, timeout=10,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
            preexec_fn=preexec_fn,
        )
        self.assertEqual(before, {p: snapshot(p) for p in before}, "input custody")
        return process

    def assert_refused(self, process, output):
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertEqual(process.stdout, b"")
        self.assertTrue(process.stderr.startswith(b"fanout preview:"), process.stderr)
        self.assertNotIn(b"Traceback", process.stderr)
        self.assertFalse(os.path.lexists(output))
        self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])

    def expected_report(self, plan_document=None, routing_document=None):
        plan_document = self.plan_document if plan_document is None else plan_document
        settings = self.routing_document if routing_document is None else routing_document
        plan = Plan.from_dict(plan_document)
        step = settings.get("step_up")
        router = EffortRouter(
            settings["catalog"], pool=tuple(Route(**row) for row in settings["pool"]),
            step_up=Route(**step) if step is not None else None,
        )
        explicit = settings.get("explicit_routes", {})
        choices = []
        for part in plan.parts:
            choice = explicit.get(part.id)
            route = router.route_for(part.id, Route(**choice) if choice is not None else None)
            choices.append({
                "part_id": part.id,
                "route": {"model": route.model, "effort": route.effort},
                "route_source": "explicit" if part.id in explicit else "pool",
                "idempotency_key": plan.idempotency_key(part.id),
            })
        return {
            "schema_version": 1,
            "plan": plan.to_dict(),
            "plan_digest": plan.digest,
            "dependency_ready_without_completions": [p.id for p in plan.ready_parts(())],
            "routes": choices,
            "configured_step_up": step,
            "input_sha256": {
                "plan": hashlib.sha256(self.plan_path.read_bytes()).hexdigest(),
                "routes": hashlib.sha256(self.routing_path.read_bytes()).hexdigest(),
            },
        }

    def test_stdout_new_file_and_repeat_match_native_apis(self):
        first = self.run_preview()
        second = self.run_preview()
        destination = self.directory / "preview.json"
        saved = self.run_preview(destination)
        for process in (first, second, saved):
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stderr, b"")
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(saved.stdout, b"")
        self.assertEqual(destination.read_bytes(), first.stdout)
        self.assertEqual(json.loads(first.stdout), self.expected_report())
        self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])

    def test_native_constructor_identity_is_preserved_and_result_is_detached(self):
        plan = Plan("constructed", (
            Part("last", "Keep native order.", ("second", "first"), ("z-tag", "a-tag", "z-tag")),
            Part("first", "First independent part."),
            Part("second", "Second independent part."),
        ))
        router = EffortRouter({"model-a": ("low",)}, pool=(Route("model-a", "low"),))
        original = copy.deepcopy(plan.to_dict())
        report = preview_plan(plan, router)
        self.assertEqual(report["plan"], original)
        self.assertEqual(report["plan_digest"], plan.digest)
        self.assertEqual(report["dependency_ready_without_completions"], ["first", "second"])
        self.assertEqual([r["part_id"] for r in report["routes"]], ["last", "first", "second"])
        for row in report["routes"]:
            self.assertEqual(row["idempotency_key"], plan.idempotency_key(row["part_id"]))
        report["plan"]["parts"][0]["tags"].clear()
        report["plan"]["parts"][0]["depends_on"].reverse()
        report["routes"][0]["route"]["effort"] = "high"
        self.assertEqual(plan.to_dict(), original)
        self.assertEqual(router.route_for("last"), Route("model-a", "low"))

    def test_helper_rejects_invalid_or_unknown_explicit_routes(self):
        plan = Plan.from_dict(self.plan_document)
        router = EffortRouter({"model-a": ("low",)}, pool=(Route("model-a", "low"),))
        for overrides in (
            {"absent": Route("model-a", "low")},
            {"finish": None},
            {"finish": Route("model-a", "max")},
        ):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                preview_plan(plan, router, explicit_routes=overrides)

    def test_omitted_and_empty_overrides_keep_native_defaults(self):
        minimal = {key: self.routing_document[key] for key in ("catalog", "pool")}
        self.write_inputs(routing=minimal)
        omitted = self.run_preview()
        self.assertEqual(omitted.returncode, 0, omitted.stderr)
        self.assertEqual(json.loads(omitted.stdout), self.expected_report(routing_document=minimal))
        explicit_empty = {**minimal, "explicit_routes": {}, "step_up": None}
        self.write_inputs(routing=explicit_empty)
        empty = self.run_preview()
        self.assertEqual(empty.returncode, 0, empty.stderr)
        self.assertEqual(json.loads(empty.stdout), self.expected_report(routing_document=explicit_empty))
        left, right = json.loads(omitted.stdout), json.loads(empty.stdout)
        left.pop("input_sha256")
        right.pop("input_sha256")
        self.assertEqual(left, right)

    def test_late_denied_route_and_malformed_documents_refuse_without_delivery(self):
        bad = []
        def route_case(label, field, value):
            settings = copy.deepcopy(self.routing_document)
            settings[field] = value
            bad.append((label, self.plan_document, settings))
        route_case("blocked explicit denial", "explicit_routes", {"finish": {"model": "model-a", "effort": "max"}})
        route_case("unknown part", "explicit_routes", {"absent": {"model": "model-a", "effort": "low"}})
        route_case("null explicit route", "explicit_routes", {"finish": None})
        route_case("unauthorized pool", "pool", [{"model": "absent", "effort": "low"}])
        route_case("empty pool", "pool", [])
        route_case("untyped route", "pool", [{"model": "model-a", "effort": ["low"]}])
        route_case("extra route field", "pool", [{"model": "model-a", "effort": "low", "extra": True}])
        route_case("invalid unused catalog pair", "catalog", {"model-a": ["low", "high"], "model-b": ["low", "high"], "unused": ["imaginary"]})
        route_case("string catalog levels", "catalog", {"model-a": "low"})
        route_case("denied step-up", "step_up", {"model": "model-a", "effort": "max"})
        route_case("unexpected routing field", "extra", True)
        cyclic = copy.deepcopy(self.plan_document)
        cyclic["parts"][1]["depends_on"] = ["finish"]
        bad += [
            ("cycle", cyclic, self.routing_document),
            ("duplicate plan key", b'{"project":"one","project":"two","parts":[]}', self.routing_document),
            ("duplicate routing key", self.plan_document, b'{"catalog":{},"pool":[],"pool":[]}'),
            ("nonfinite JSON", b'{"project":NaN,"parts":[]}', self.routing_document),
            ("invalid UTF-8", b"\xff", self.routing_document),
            ("syntax error", b"{", self.routing_document),
            ("deep JSON", b"[" * 2000 + b"0" + b"]" * 2000, self.routing_document),
        ]
        for index, (label, plan, settings) in enumerate(bad):
            with self.subTest(label=label):
                self.write_inputs(plan=plan, routing=settings)
                destination = self.directory / f"rejected-{index}.json"
                self.assert_refused(self.run_preview(destination), destination)

    def test_exact_input_byte_limits_and_one_byte_over(self):
        plan = encoded(self.plan_document)
        routes = encoded(self.routing_document)
        plan += b" " * (MAX_PLAN_BYTES - len(plan))
        routes += b" " * (MAX_ROUTING_BYTES - len(routes))
        self.write_inputs(plan=plan, routing=routes)
        exact = self.run_preview()
        self.assertEqual(exact.returncode, 0, exact.stderr)
        self.assertEqual(json.loads(exact.stdout), self.expected_report())
        for label, plan_input, route_input in (
            ("plan", plan + b" ", routes),
            ("routes", plan, routes + b" "),
        ):
            with self.subTest(label=label):
                self.write_inputs(plan=plan_input, routing=route_input)
                destination = self.directory / (label + "-too-large.json")
                self.assert_refused(self.run_preview(destination), destination)

    def test_maximum_chain_and_part_limit(self):
        parts = [
            {
                "id": f"node{i:03d}", "instruction": "Keep the native graph.",
                "depends_on": [f"node{i + 1:03d}"] if i < 255 else [],
            }
            for i in range(256)
        ]
        plan = {"project": "long-chain", "parts": parts}
        settings = {key: self.routing_document[key] for key in ("catalog", "pool")}
        self.write_inputs(plan=plan, routing=settings)
        exact = self.run_preview()
        self.assertEqual(exact.returncode, 0, exact.stderr)
        self.assertEqual(json.loads(exact.stdout), self.expected_report(plan, settings))
        self.assertEqual(json.loads(exact.stdout)["dependency_ready_without_completions"], ["node255"])
        over = {"project": "long-chain", "parts": parts + [{"id": "extra", "instruction": "One too many."}]}
        self.write_inputs(plan=over, routing=settings)
        destination = self.directory / "too-many-parts.json"
        self.assert_refused(self.run_preview(destination), destination)

    def test_model_and_pool_limits_preserve_native_pool_selection(self):
        settings = {
            "catalog": {f"model-{i:03d}": ["low"] for i in range(256)},
            "pool": [{"model": f"model-{i:03d}", "effort": "low"} for i in range(256)],
        }
        self.write_inputs(routing=settings)
        exact = self.run_preview()
        self.assertEqual(exact.returncode, 0, exact.stderr)
        self.assertEqual(json.loads(exact.stdout), self.expected_report(routing_document=settings))
        for field in ("catalog", "pool"):
            over = copy.deepcopy(settings)
            if field == "catalog":
                over[field]["extra-model"] = ["low"]
            else:
                over[field].append(copy.deepcopy(over[field][0]))
            self.write_inputs(routing=over)
            destination = self.directory / ("too-many-" + field + ".json")
            self.assert_refused(self.run_preview(destination), destination)

    def test_helper_report_limit(self):
        plan = Plan("large-report", (Part("one", "x" * MAX_REPORT_BYTES),))
        router = EffortRouter({"model-a": ("low",)}, pool=(Route("model-a", "low"),))
        with self.assertRaises(PreviewError):
            preview_plan(plan, router)

    def test_existing_file_input_directory_and_missing_parent_are_preserved(self):
        prior = self.directory / "prior.json"
        prior.write_bytes(b"retained output\n")
        directory = self.directory / "prior-directory"
        directory.mkdir()
        marker = directory / "retained.txt"
        marker.write_bytes(b"retained directory body\n")
        before = {path: snapshot(path) for path in (prior, marker, self.plan_path, self.routing_path)}
        for destination in (prior, self.plan_path, directory, self.directory / "missing" / "new.json"):
            with self.subTest(destination=destination.name):
                process = self.run_preview(destination)
                self.assertEqual(process.returncode, 2, process.stderr)
                self.assertEqual(process.stdout, b"")
                self.assertNotIn(b"Traceback", process.stderr)
                self.assertEqual(before, {path: snapshot(path) for path in before})
                self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])
        self.assertFalse((self.directory / "missing").exists())

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_existing_and_dangling_output_symlinks_are_not_followed(self):
        for name, target in (("source-link", self.plan_path), ("dangling-link", self.directory / "absent")):
            link = self.directory / name
            try:
                link.symlink_to(target)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable in this environment: {exc}")
            before = os.readlink(link)
            process = self.run_preview(link)
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assertEqual(process.stdout, b"")
            self.assertEqual(os.readlink(link), before)
            self.assertEqual(list(self.directory.glob(".fanout-preview-*")), [])
        self.assertFalse((self.directory / "absent").exists())

    @unittest.skipUnless(os.name == "posix", "requires native POSIX file-size limit")
    def test_kernel_write_failure_leaves_no_output_or_stage(self):
        import resource
        import signal
        def limited_file_size():
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            resource.setrlimit(resource.RLIMIT_FSIZE, (512, 512))
        destination = self.directory / "failed-write.json"
        self.assert_refused(self.run_preview(destination, preexec_fn=limited_file_size), destination)

    @unittest.skipUnless(Path("/dev/full").exists(), "requires native /dev/full")
    def test_stdout_failure_is_an_io_refusal_without_shutdown_traceback(self):
        with open("/dev/full", "wb") as full:
            process = self.run_preview(stdout=full)
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertNotIn(b"Traceback", process.stderr)
        self.assertNotIn(b"Exception ignored", process.stderr)
        self.assertTrue(process.stderr.startswith(b"fanout preview:"))
        self.assertEqual(set(self.directory.iterdir()), {self.plan_path, self.routing_path})

    @unittest.skipUnless(hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"), "requires native nonblocking FIFO")
    def test_nonregular_input_is_refused_without_blocking(self):
        self.plan_path.unlink()
        os.mkfifo(self.plan_path)
        process = subprocess.run(
            [sys.executable, "-B", "-m", "fanout_engine.preview",
             "--plan", str(self.plan_path), "--routes", str(self.routing_path)],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10,
            env={**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertEqual(process.stdout, b"")
        self.assertIn(b"regular file", process.stderr)
        self.assertNotIn(b"Traceback", process.stderr)

    def test_actual_cli_with_connection_and_spawn_operations_denied(self):
        source_paths = sorted((ROOT / "fanout_engine").glob("*.py"))
        before = {path: snapshot(path) for path in source_paths}
        process = self.run_preview(audit=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout), self.expected_report())
        self.assertEqual(before, {path: snapshot(path) for path in source_paths})
        self.assertEqual(set(self.directory.iterdir()), {self.plan_path, self.routing_path})


if __name__ == "__main__":
    unittest.main()
