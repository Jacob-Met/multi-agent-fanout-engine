"""Worker assignments must have usable literal identities before local dispatch admission."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from fanout_engine import EffortRouter, Ledger, Plan, Route, dispatch_ready
from fanout_engine.ledger import LedgerError


ROUTE = {"model": "model-a", "effort": "low"}


class MisleadingText(str):
    def strip(self, *args):
        return "not blank"

    def encode(self, *args, **kwargs):
        return b"pretend UTF-8"


class AdaptingText(str):
    def __str__(self):
        return "substituted-by-str"

    def __conform__(self, protocol):
        return " "


class FalseText(str):
    def __bool__(self):
        return False


class RecordingHub:
    def __init__(self):
        self.calls = []

    def submit(self, part, **kwargs):
        self.calls.append((part.id, kwargs.copy()))
        return {"task_id": "local-task-" + part.id}


def plan(*ids):
    return Plan.from_dict({"project": "worker-identity", "parts": [
        {"id": part_id, "instruction": "Fictional local work."} for part_id in ids
    ]})


def router():
    return EffortRouter({"model-a": ("low",)}, pool=(Route("model-a", "low"),))


INVALID = (None, "", " ", "\t\n", "\u2003", 7, True, 1.5, b"worker-a",
           ["worker-a"], {"worker": "a"}, "\ud800", "worker-\udfff",
           MisleadingText(" \t"), MisleadingText("\ud800"))
VALID = ("worker-a", "  worker-雪\t", "worker-Ω", "line\nbreak",
         "worker\x00literal", MisleadingText("worker-valid"), FalseText("worker-valid"), AdaptingText("worker-雪"))


class WorkerIdentityTests(unittest.TestCase):
    def test_direct_rejection_preserves_exact_state_and_events(self):
        for worker_id in INVALID:
            with self.subTest(worker_id=repr(worker_id)), Ledger() as ledger:
                authored = plan("draft")
                ledger.record_plan(authored)
                before = (ledger.part(authored.project_id, "draft"), ledger.events(authored.project_id))
                with self.assertRaisesRegex(LedgerError, "worker id"):
                    ledger.mark_dispatching(authored.project_id, "draft", worker_id, ROUTE)
                self.assertEqual((ledger.part(authored.project_id, "draft"),
                                  ledger.events(authored.project_id)), before)

    def test_dispatch_rejects_before_adapter_and_keeps_assignment_retryable(self):
        for worker_id in INVALID:
            with self.subTest(worker_id=repr(worker_id)), Ledger() as ledger:
                authored, hub = plan("draft"), RecordingHub()
                with self.assertRaisesRegex(LedgerError, "worker id"):
                    dispatch_ready(authored, ledger, hub, router(), worker_for=lambda _: worker_id)
                self.assertEqual(hub.calls, [])
                self.assertEqual(ledger.part_state(authored.project_id, "draft"), "queued")
                self.assertEqual([e["event"] for e in ledger.events(authored.project_id)], ["plan_recorded"])
                retried = dispatch_ready(authored, ledger, hub, router(), worker_for=lambda _: "worker-corrected")
                self.assertEqual(retried.started, ("draft",))
                self.assertEqual(len(hub.calls), 1)
                self.assertEqual(hub.calls[0][1]["worker_id"], "worker-corrected")

    def test_valid_literals_survive_adapter_storage_events_and_cli_reopen(self):
        package = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="fanout-worker-") as directory:
            for index, worker_id in enumerate(VALID):
                with self.subTest(worker_id=repr(worker_id)):
                    database = Path(directory) / (str(index) + ".sqlite3")
                    authored, hub = plan("draft"), RecordingHub()
                    with Ledger(str(database)) as ledger:
                        result = dispatch_ready(authored, ledger, hub, router(), worker_for=lambda _: worker_id)
                        self.assertEqual(result.started, ("draft",))
                        self.assertIs(hub.calls[0][1]["worker_id"], worker_id)
                        self.assertEqual(ledger.part(authored.project_id, "draft")["worker_id"], worker_id)
                        self.assertEqual(ledger.events(authored.project_id)[1]["detail"]["worker_id"], worker_id)
                    before_bytes = database.read_bytes()
                    completed = subprocess.run(
                        [sys.executable, "-B", "-m", "fanout_engine.inspect", "--database", str(database),
                         "--project", authored.project_id],
                        cwd=package, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                        capture_output=True, timeout=10,
                    )
                    self.assertEqual(completed.returncode, 0, completed.stderr)
                    report = json.loads(completed.stdout)
                    self.assertEqual(report["parts"][0]["worker_id"], worker_id)
                    self.assertEqual(database.read_bytes(), before_bytes)

    def test_later_invalid_assignment_does_not_replay_an_earlier_dispatch(self):
        authored, hub = plan("first", "second", "third"), RecordingHub()
        with Ledger() as ledger:
            with self.assertRaisesRegex(LedgerError, "worker id"):
                dispatch_ready(authored, ledger, hub, router(),
                               worker_for=lambda part: "worker-a" if part.id == "first" else " ")
            self.assertEqual([call[0] for call in hub.calls], ["first"])
            self.assertEqual(ledger.part_state(authored.project_id, "first"), "running")
            self.assertEqual(ledger.part_state(authored.project_id, "second"), "queued")
            self.assertEqual(ledger.part_state(authored.project_id, "third"), "queued")
            result = dispatch_ready(authored, ledger, hub, router(), worker_for=lambda _: "worker-corrected")
            self.assertEqual(result.started, ("second", "third"))
            self.assertEqual([call[0] for call in hub.calls], ["first", "second", "third"])


if __name__ == "__main__":
    unittest.main()
