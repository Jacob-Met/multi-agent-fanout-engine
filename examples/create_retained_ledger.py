"""Create a new authored sample database for the read-only inspection CLI."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fanout_engine import Ledger, Part, Plan


def create_sample(database: Path) -> None:
    # An explicit new file keeps a demonstration from replacing real work.
    database.touch(exist_ok=False)
    plan = Plan("sample", (
        Part("source", "Use the accepted example source.", tags=("example", "source")),
        Part("draft", "An authored example of running work."),
        Part("verify", "An authored ambiguous acceptance that needs evidence."),
        Part("rejected", "An authored example with confirmed failure."),
        Part("acknowledge", "An authored dispatch awaiting a durable acknowledgement."),
        Part("notes", "Document the accepted source.", depends_on=("source",)),
        Part("publish", "Wait for the draft and verified evidence.", depends_on=("draft", "verify")),
    ))
    route = {"model": "example-model", "effort": "low"}
    evidence = {
        "source": "authored local demonstration",
        "locator": "example:retained-ledger",
        "finding": "Synthetic state only; no remote work was executed.",
    }
    with Ledger(str(database.absolute())) as ledger:
        ledger.record_plan(plan)
        for part_id in ("source", "draft", "verify", "rejected", "acknowledge"):
            ledger.mark_dispatching("sample", part_id, "example-worker", route)
        for part_id in ("source", "draft"):
            ledger.mark_running("sample", part_id, "example-task-" + part_id)
        ledger.mark_completed("sample", "source", "example:accepted-source", evidence)
        for part_id in ("verify", "rejected"):
            ledger.mark_outcome_unknown("sample", part_id, evidence)
        ledger.reconcile_unknown("sample", "rejected", verdict="failed", evidence=evidence)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="new sample SQLite file; must not already exist")
    args = parser.parse_args()
    try:
        create_sample(args.database)
    except OSError as exc:
        print(f"sample ledger: {exc}", file=sys.stderr)
        return 2
    message = f"Created authored sample project 'sample' in {args.database}"
    try:
        print(message)
    except UnicodeEncodeError:
        # Keep the real path intact; escape only its unprintable diagnostic text.
        escaped = message.encode(sys.stdout.encoding, "backslashreplace")
        print(escaped.decode(sys.stdout.encoding))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
