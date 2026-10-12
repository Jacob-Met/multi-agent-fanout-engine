"""Native producer and receiving checks for explicitly selected authored work."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import EffortRouter, Ledger, Part, Plan, PlanError, Route, inspect_project
from fanout_engine.plan import canonical_json
from fanout_engine.preview import preview_plan
from fanout_engine.subplan import MAX_PLAN_BYTES, SubplanError, select_subplan

SOURCE = Path(__file__).resolve().parents[1]


def authored_plan() -> Plan:
    return Plan("Original", (
        Part("publish", "Publish café and 漢字.\nKeep this exact.", ("review", "layout"), ("z", "z", "a")),
        Part("unused", "Keep unrelated work separate."),
        Part("research", "Read the source."),
        Part("layout", "Lay out the result.", ("research",)),
        Part("review", "Review the draft.", ("research",)),
    ))


def encoded(plan: Plan) -> bytes:
    return (canonical_json(plan.to_dict()) + "\n").encode("utf-8")


def cli(path: Path, *arguments: str, stdout=subprocess.PIPE) -> subprocess.CompletedProcess:
    command = [sys.executable, "-B"] + (["-O"] if sys.flags.optimize else [])
    command += ["-m", "fanout_engine.subplan", "--plan", str(path), *arguments]
    return subprocess.run(
        command, cwd=path.parent, stdout=stdout, stderr=subprocess.PIPE, timeout=10,
        env={**os.environ, "PYTHONPATH": str(SOURCE), "PYTHONDONTWRITEBYTECODE": "1"},
    )


class SubplanTests(unittest.TestCase):
    def test_shared_dependency_closure_retains_exact_authored_rows_and_order(self):
        original = authored_plan()
        before = encoded(original)
        selected = select_subplan(original, ["publish", "review"], "Reuse")
        expected = Plan("Reuse", tuple(p for p in original.parts if p.id != "unused"))
        self.assertEqual(selected, expected)
        self.assertEqual([p.id for p in selected.parts], ["publish", "research", "layout", "review"])
        self.assertEqual(selected.parts[0].depends_on, ("review", "layout"))
        self.assertEqual(selected.parts[0].tags, ("z", "z", "a"))
        self.assertEqual(select_subplan(original, ("review", "publish"), "Reuse"), expected)
        self.assertEqual(select_subplan(original, ["research"], "RootOnly").parts, (original.parts[2],))
        self.assertEqual(encoded(original), before)
        original_by_id = {part.id: part for part in original.parts}
        self.assertTrue(all(part is not original_by_id[part.id] for part in selected.parts))

    def test_complete_output_is_received_by_native_preview_and_retained_ledger(self):
        original = authored_plan()
        selected = select_subplan(original, ["publish"], "Reuse")
        wire = json.dumps(selected.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        digest = hashlib.sha256(wire.encode()).hexdigest()
        self.assertEqual(selected.digest, digest)
        keys = {
            p.id: "fanout-" + hashlib.sha256(("Reuse\0" + digest + "\0" + p.id).encode()).hexdigest()
            for p in selected.parts
        }
        route = Route("authored-offline", "high")
        router = EffortRouter({route.model: (route.effort,)}, pool=(route,))
        preview = preview_plan(selected, router)
        self.assertEqual(preview["plan"], selected.to_dict())
        self.assertEqual(preview["dependency_ready_without_completions"], ["research"])
        self.assertEqual([r["idempotency_key"] for r in preview["routes"]], list(keys.values()))
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "native.sqlite3"
            with Ledger(str(path)) as ledger:
                self.assertTrue(ledger.record_plan(original))
                original_rows = ledger.project_snapshot("Original")
                self.assertTrue(ledger.record_plan(selected))
                self.assertFalse(ledger.record_plan(selected))
                for part_id, key in keys.items():
                    self.assertEqual(ledger.idempotency_key("Reuse", part_id), key)
                    self.assertNotEqual(key, ledger.idempotency_key("Original", part_id))
                received = inspect_project(ledger, "Reuse")
                self.assertEqual(ledger.project_snapshot("Original"), original_rows)
            before = path.read_bytes()
            with Ledger.open_readonly(path) as ledger:
                self.assertEqual(inspect_project(ledger, "Reuse"), received)
                self.assertEqual(ledger.project_snapshot("Original"), original_rows)
            self.assertEqual(path.read_bytes(), before)

    def test_explicit_selection_and_new_project_are_required(self):
        original = authored_plan()
        invalid = [[], ["publish", "publish"], ["missing"], ["Publish"], [None],
                   "publish", b"publish", None, {"publish"}, iter(["publish"])]
        for selection in invalid:
            with self.subTest(selection=repr(selection)), self.assertRaises(SubplanError):
                select_subplan(original, selection, "Reuse")
        with self.assertRaisesRegex(SubplanError, "differ"):
            select_subplan(original, ["publish"], "Original")
        for project in ("", "bad project", "9startsWithNumber", None):
            with self.subTest(project=project), self.assertRaises(PlanError):
                select_subplan(original, ["publish"], project)
        with self.assertRaises(SubplanError):
            select_subplan(original.to_dict(), ["publish"], "Reuse")

    def test_capture_detaches_mutable_values_and_checks_unselected_source(self):
        class MutablePart:
            def __init__(self):
                self.id = "mutable"
                self.instruction = "Keep original text."
                self.depends_on = ["root"]
                self.tags = ["z", "z", "a"]

            def to_dict(self):
                return {"id": self.id, "instruction": self.instruction,
                        "depends_on": self.depends_on, "tags": self.tags}

        mutable = MutablePart()
        original = Plan("Original", (Part("root", "Read."), mutable))
        result = select_subplan(original, ["mutable"], "Reuse")
        self.assertIs(type(result.parts[1]), Part)
        retained = encoded(result)
        mutable.instruction = "Later changed text."
        mutable.tags.clear()
        self.assertEqual(encoded(result), retained)
        with self.assertRaisesRegex(SubplanError, "changed since validation"):
            select_subplan(original, ["root"], "Other")
        mutable.depends_on.append("missing")
        with self.assertRaisesRegex(PlanError, "unknown part"):
            select_subplan(original, ["root"], "Other")

    def test_large_source_and_deep_dependency_boundaries(self):
        wide = Plan("Wide", tuple(Part(f"p{i}", "Work.") for i in range(4096)))
        self.assertEqual([p.id for p in select_subplan(wide, ["p4095"], "Single").parts], ["p4095"])
        too_wide = Plan("Wide", (*wide.parts, Part("extra", "Work.")))
        with self.assertRaisesRegex(SubplanError, "4096"):
            select_subplan(too_wide, ["p0"], "Single")
        deep = Plan("Deep", tuple(reversed(tuple(
            Part(f"p{i}", "Work.", (f"p{i-1}",) if i else ()) for i in range(1500)
        ))))
        selected = select_subplan(deep, ["p255"], "Bounded")
        self.assertEqual([p.id for p in selected.parts], [f"p{i}" for i in reversed(range(256))])
        self.assertEqual([p.id for p in selected.ready_parts()], ["p0"])
        with self.assertRaisesRegex(SubplanError, "closure exceeds"):
            select_subplan(deep, ["p256"], "TooMany")

    def test_cli_emits_only_native_plan_from_literal_path(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "source $ literal # café (1).json"
            raw = encoded(authored_plan())
            path.write_bytes(raw)
            sentinel = Path(td) / "saved.sqlite3"
            sentinel.write_bytes(b"retained bytes\x00\xff")
            result = cli(path, "--part", "publish", "--project", "Reuse")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, b"")
            parsed = Plan.from_dict(json.loads(result.stdout))
            normalized = Plan.from_dict(authored_plan().to_dict())
            expected = Plan("Reuse", tuple(p for p in normalized.parts if p.id != "unused"))
            self.assertEqual(parsed, expected)
            self.assertEqual(result.stdout, encoded(expected))
            self.assertEqual(set(json.loads(result.stdout)), {"project", "parts"})
            again = cli(path, "--part", "publish", "--project", "Reuse")
            self.assertEqual(result.stdout, again.stdout)
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(sentinel.read_bytes(), b"retained bytes\x00\xff")
            self.assertEqual(sorted(p.name for p in Path(td).iterdir()), sorted([path.name, sentinel.name]))

    def test_cli_validates_hidden_source_and_malformed_text_before_output(self):
        base = {"project": "Source", "parts": [{"id": "keep", "instruction": "Keep."}]}
        bad_hidden = {**base, "parts": [*base["parts"], {"id": "unused", "instruction": "Bad.", "depends_on": ["absent"]}]}
        cases = [json.dumps(bad_hidden).encode(),
                 b'{"project":"Source","project":"Source","parts":[]}',
                 b'{"project":"Source","parts":[{"id":"keep","instruction":"\\ud800"}]}',
                 b'{"project":"Source","parts":[] ,"extra":1e9999}',
                 b'[' * 3000 + b'0' + b']' * 3000, b'\xff']
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "source.json"
            for raw in cases:
                with self.subTest(raw=raw[:100]):
                    path.write_bytes(raw)
                    result = cli(path, "--part", "keep", "--project", "Reuse")
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertEqual(result.stdout, b"")
                    self.assertNotIn(b"Traceback", result.stderr)
                    self.assertEqual(path.read_bytes(), raw)

    def test_cli_input_and_complete_result_byte_boundaries(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "source.json"
            small = encoded(Plan("From", (Part("keep", "x"),)))
            path.write_bytes(small + b" " * (MAX_PLAN_BYTES - len(small)))
            result = cli(path, "--part", "keep", "--project", "Dest")
            self.assertEqual(result.returncode, 0, result.stderr)
            path.write_bytes(path.read_bytes() + b" ")
            result = cli(path, "--part", "keep", "--project", "Dest")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, b"")
            overhead = len(encoded(Plan("Dest", (Part("keep", "x"),)))) - 1
            for delta, status in ((0, 0), (1, 2)):
                instruction = "x" * (MAX_PLAN_BYTES - overhead + delta)
                minimal = {"project": "From", "parts": [{"id": "keep", "instruction": instruction}]}
                raw = json.dumps(minimal, separators=(",", ":")).encode()
                self.assertLessEqual(len(raw), MAX_PLAN_BYTES)
                path.write_bytes(raw)
                result = cli(path, "--part", "keep", "--project", "Dest")
                self.assertEqual(result.returncode, status, result.stderr)
                self.assertEqual(len(result.stdout), MAX_PLAN_BYTES if status == 0 else 0)
                self.assertEqual(path.read_bytes(), raw)

    def test_cli_selection_and_usage_refusals_emit_no_plan(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "source.json"
            path.write_bytes(encoded(authored_plan()))
            for arguments in (("--part", "unknown", "--project", "Reuse"),
                              ("--part", "publish", "--part", "publish", "--project", "Reuse"),
                              ("--part", "publish", "--project", "Original"),
                              ("--part", "publish", "--pro", "Reuse")):
                with self.subTest(arguments=arguments):
                    result = cli(path, *arguments)
                    self.assertEqual(result.returncode, 2)
                    self.assertEqual(result.stdout, b"")
                    self.assertNotIn(b"Traceback", result.stderr)

    def test_nonregular_input_does_not_wait_and_failed_output_returns_one(self):
        with tempfile.TemporaryDirectory() as td:
            if hasattr(os, "mkfifo"):
                fifo = Path(td) / "source.fifo"
                os.mkfifo(fifo)
                refused = cli(fifo, "--part", "keep", "--project", "Reuse")
                self.assertEqual(refused.returncode, 2)
                self.assertEqual(refused.stdout, b"")
            if Path("/dev/full").exists():
                path = Path(td) / "source.json"
                path.write_bytes(encoded(authored_plan()))
                with open("/dev/full", "wb") as sink:
                    failed = cli(path, "--part", "publish", "--project", "Reuse", stdout=sink)
                self.assertEqual(failed.returncode, 1, failed.stderr)
                self.assertNotIn(b"Traceback", failed.stderr)


if __name__ == "__main__":
    unittest.main()
