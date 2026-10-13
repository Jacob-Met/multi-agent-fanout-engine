"""Receive the authored blocker report after a real queued withdrawal."""
from pathlib import Path
import tempfile
import unittest

from fanout_engine.blockers import inspect_blockers
from fanout_engine.ledger import Ledger
from fanout_engine.plan import Plan


def observe_files(paths):
    return {
        str(path): (path.read_bytes(), path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(paths)
    }


class WithdrawnBlockerTests(unittest.TestCase):
    def test_withdrawal_is_a_failed_frontier_without_changing_retained_data(self):
        # Declaration order differs from graph order and direct dependency order.
        plan = Plan.from_dict({
            "project": "withdrawal-blocker-fixture",
            "parts": [
                {"id": "release", "instruction": "Receive both fictional branches.",
                 "depends_on": ["right", "left"]},
                {"id": "withdrawn", "instruction": "Work no longer requested.",
                 "depends_on": ["ancestor"]},
                {"id": "left", "instruction": "First fictional branch.",
                 "depends_on": ["withdrawn"]},
                {"id": "right", "instruction": "Second fictional branch.",
                 "depends_on": ["withdrawn"]},
                {"id": "ancestor", "instruction": "Unused ready prerequisite."},
                {"id": "independent", "instruction": "Unrelated ready work."},
            ],
        })
        evidence = {
            "source": "fictional request owner",
            "locator": "fixture:withdrawal/one",
            "finding": "  This queued work is no longer requested.  ",
        }
        project = plan.project_id
        source_root = Path(__file__).resolve().parents[1] / "fanout_engine"
        source_paths = [Path(__file__).resolve(), *source_root.rglob("*.py")]
        source_before = observe_files(source_paths)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "ledger.sqlite3"
            with Ledger(str(database)) as writer:
                writer.record_plan(plan)
                self.assertEqual(writer.part_state(project, "withdrawn"), "queued")
                writer.withdraw_queued(project, "withdrawn", evidence)

            # Take the preservation boundary after the intentional withdrawal.
            files_before = observe_files(root.iterdir())
            with Ledger.open_readonly(database) as reader:
                withdrawn = reader.part(project, "withdrawn")
                self.assertEqual(withdrawn["state"], "failed")
                self.assertEqual(withdrawn["evidence"], evidence)
                for key in ("worker_id", "task_id", "route_json", "artifact_ref"):
                    self.assertIsNone(withdrawn[key], key)
                events = reader.events(project, "withdrawn")
                self.assertEqual([event["event"] for event in events],
                                 ["queued_withdrawn"])
                self.assertEqual(events[0]["detail"], evidence)
                project_before = reader.project_snapshot(project)
                events_before = reader.project_event_snapshot(project)
                changes_before = reader._db.total_changes

                report = inspect_blockers(reader, project)

                # The failed part stops traversal even though its ancestor is ready.
                # The shared diamond reaches release twice but reports it once.
                self.assertEqual(report, {
                    "schema_version": 1,
                    "project_id": project,
                    "plan_digest": plan.digest,
                    "queued_ready_ids": ["ancestor", "independent"],
                    "blocked_queued": [
                        {"id": "release", "direct_unmet_ids": ["right", "left"],
                         "frontier_ids": ["withdrawn"]},
                        {"id": "left", "direct_unmet_ids": ["withdrawn"],
                         "frontier_ids": ["withdrawn"]},
                        {"id": "right", "direct_unmet_ids": ["withdrawn"],
                         "frontier_ids": ["withdrawn"]},
                    ],
                    "frontier": [
                        {"id": "withdrawn", "state": "failed",
                         "worker_id": None, "task_id": None,
                         "blocked_queued_ids": ["release", "left", "right"]},
                    ],
                })
                self.assertEqual(reader.project_snapshot(project), project_before)
                self.assertEqual(reader.project_event_snapshot(project), events_before)
                self.assertEqual(reader._db.total_changes, changes_before)
                self.assertFalse(reader._db.in_transaction)
            self.assertEqual(observe_files(root.iterdir()), files_before)
        self.assertEqual(
            observe_files([Path(__file__).resolve(), *source_root.rglob("*.py")]),
            source_before,
        )


if __name__ == "__main__":
    unittest.main()
