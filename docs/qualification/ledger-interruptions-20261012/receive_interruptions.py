"""Independent disk-backed consumer: interrupt after an event is written."""
import argparse
import json
from pathlib import Path
import signal
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    from fanout_engine import Ledger, Plan, inspect_project

    class InterruptingLedger(Ledger):
        interrupt_event = None

        def _event(self, db, project_id, part_id, event, detail):
            super()._event(db, project_id, part_id, event, detail)
            if event == self.interrupt_event:
                signal.raise_signal(signal.SIGINT)

    outcomes = []
    plan = Plan.from_dict({"project": "disk-interruption", "parts": [
        {"id": "first", "instruction": "local first"},
        {"id": "next", "instruction": "local next", "depends_on": ["first"]},
    ]})
    route = {"model": "local-test", "effort": "low"}
    for event in ("plan_recorded", "dispatch_started", "dispatch_accepted", "completed"):
        with tempfile.TemporaryDirectory(prefix="fanout-signal-") as folder:
            database = str(Path(folder) / "consumer.sqlite")
            with InterruptingLedger(database) as ledger:
                if event != "plan_recorded":
                    ledger.record_plan(plan)
                if event in ("dispatch_accepted", "completed"):
                    ledger.mark_dispatching(plan.project_id, "first", "local-worker", route)
                if event == "completed":
                    ledger.mark_running(plan.project_id, "first", "local-task")
                before = ledger.project_snapshot(plan.project_id)
                before_events = ledger.events(plan.project_id)
                ledger.interrupt_event = event
                propagated = False
                try:
                    if event == "plan_recorded":
                        ledger.record_plan(plan)
                    elif event == "dispatch_started":
                        ledger.mark_dispatching(plan.project_id, "first", "local-worker", route)
                    elif event == "dispatch_accepted":
                        ledger.mark_running(plan.project_id, "first", "local-task")
                    else:
                        ledger.mark_completed(plan.project_id, "first", "local-artifact:one")
                except KeyboardInterrupt:
                    propagated = True
                # This public read uses the connection context in the product.
                # On the predecessor it commits the leaked interrupted write.
                try:
                    ledger.part_state(plan.project_id, "first")
                except Exception:
                    pass
            with Ledger(database) as reopened:
                snapshot_unchanged = reopened.project_snapshot(plan.project_id) == before
                events_unchanged = reopened.events(plan.project_id) == before_events
                if before is not None and snapshot_unchanged:
                    report = inspect_project(reopened, plan.project_id)
                    if event == "dispatch_accepted":
                        assert report["state_counts"]["dispatching"] == 1
                        assert reopened.mark_interrupted_dispatches_unknown(plan.project_id) == 1
                        assert reopened.part_state(plan.project_id, "first") == "outcome_unknown"
                        assert "first" not in reopened.dispatchable_ids(plan.project_id)
                outcomes.append({"event": event, "signal_propagated": propagated,
                                 "snapshot_unchanged_after_public_read_and_reopen": snapshot_unchanged,
                                 "events_unchanged_after_reopen": events_unchanged})
    print(json.dumps({"python": sys.version.split()[0], "courses": outcomes}, indent=2))
    return 0 if all(all(v for k, v in row.items() if k != "event") for row in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
