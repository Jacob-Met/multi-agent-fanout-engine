"""Create a new queued ledger from an authored Plan JSON file."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

from .compare import _read_plan
from .inspect import _write_stdout
from .ledger import Ledger
from .plan import canonical_json
from .preview import _publish_new_file

_SIDECAR_SUFFIXES = ("-wal", "-shm", "-journal")


def _prepare_database(plan_path: Path, database: Path) -> tuple[bytes, bytes]:
    plan, input_digest = _read_plan(plan_path, "plan")
    with tempfile.TemporaryDirectory(prefix="fanout-new-ledger-") as temporary:
        staged = Path(temporary) / "ledger.sqlite3"
        with Ledger(str(staged)) as ledger:
            ledger.record_plan(plan)
        content = staged.read_bytes()
    # Complete encoding before destination publication, including literal paths.
    receipt = {
        "schema_version": 1,
        "database": str(database),
        "project_id": plan.project_id,
        "plan_digest": plan.digest,
        "part_count": len(plan.parts),
        "input_sha256": input_digest,
        "database_sha256": hashlib.sha256(content).hexdigest(),
    }
    return content, (canonical_json(receipt) + "\n").encode("utf-8")


def _check_database_destination(database: Path) -> None:
    if database.name.lower().endswith(_SIDECAR_SUFFIXES):
        raise ValueError("database filename must not end in -wal, -shm or -journal")
    for suffix in _SIDECAR_SUFFIXES:
        if os.path.lexists(str(database) + suffix):
            raise ValueError("database destination has an existing SQLite sidecar")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create a new queued SQLite ledger from an authored Plan; do not dispatch work.",
        allow_abbrev=False,
    )
    parser.add_argument("--plan", type=Path, required=True, help="authored Plan JSON file")
    parser.add_argument("--database", type=Path, required=True, help="new SQLite file; must not exist")
    args = parser.parse_args(argv)
    try:
        content, receipt = _prepare_database(args.plan, args.database)
    except RecursionError:
        print("fanout create ledger: input nesting exceeds consumer limits", file=sys.stderr)
        return 2
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f"fanout create ledger: preparation failed before publication: {exc}", file=sys.stderr)
        return 2
    try:
        _check_database_destination(args.database)
        _publish_new_file(args.database, content)
    except (ValueError, OSError) as exc:
        print(
            f"fanout create ledger: database publication did not complete normally: {exc}; "
            "inspect the destination before retrying",
            file=sys.stderr,
        )
        return 1
    try:
        _write_stdout(receipt)
    except OSError as exc:
        print(
            f"fanout create ledger: database was published; confirmation output failed: {exc}; "
            "inspect the destination before retrying",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
