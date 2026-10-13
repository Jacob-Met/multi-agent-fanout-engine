"""Inspect a retained project from an explicitly selected read-only database."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sqlite3
import sys
import unicodedata

from .inspection import InspectionError, inspect_project
from .ledger import Ledger, LedgerError
from .plan import canonical_json
from .preview import PreviewError, _publish_new_file


_SQLITE_SIDECARS = ("-wal", "-shm", "-journal")


def _path_key(path: Path) -> str:
    try:
        resolved = path.resolve()
    except RuntimeError as exc:
        raise ValueError("output path cannot be resolved") from exc
    # Be conservative on case-insensitive or Unicode-normalizing filesystems,
    # including when the reserved sidecar does not exist yet.
    return unicodedata.normalize("NFC", str(resolved)).casefold()


def _check_output_path(database: Path, destination: Path) -> None:
    if os.path.lexists(destination):
        raise ValueError("output already exists; choose a new file")
    destination_key = _path_key(destination)
    for database_name in (database.absolute(), database.resolve()):
        for suffix in ("", *_SQLITE_SIDECARS):
            if destination_key == _path_key(Path(str(database_name) + suffix)):
                raise ValueError("output is a database or SQLite sidecar path")
    # A hard link can give the selected database another name which resolve()
    # cannot discover. Check an output's existing unsuffixed file directly.
    for suffix in _SQLITE_SIDECARS:
        if str(destination).casefold().endswith(suffix):
            sibling = Path(str(destination)[:-len(suffix)])
            try:
                same_database = os.path.samefile(sibling, database)
            except (FileNotFoundError, NotADirectoryError):
                same_database = False
            if same_database:
                raise ValueError("output is a database or SQLite sidecar path")


def _write_stdout(content: bytes) -> None:
    if sys.stdout is None:
        raise OSError("standard output is unavailable")
    try:
        sys.stdout.buffer.write(content)
        sys.stdout.buffer.flush()
    except OSError:
        # A stream can have received a prefix already. Prevent interpreter
        # shutdown from attempting the same failed buffered flush a second time.
        try:
            with open(os.devnull, "wb") as sink:
                os.dup2(sink.fileno(), sys.stdout.fileno())
        except OSError:
            pass
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect one retained fanout project without changing its ledger or dispatching work.",
        allow_abbrev=False,
    )
    parser.add_argument("--database", type=Path, required=True, help="existing SQLite ledger file")
    parser.add_argument("--project", required=True, help="exact recorded project identifier")
    parser.add_argument("--output", type=Path, help="new report file; otherwise write JSON to stdout")
    args = parser.parse_args(argv)
    try:
        with Ledger.open_readonly(args.database) as ledger:
            report = inspect_project(ledger, args.project)
        # Complete native validation and encoding precede any success output.
        content = (canonical_json(report) + "\n").encode("utf-8")
    except InspectionError as exc:
        print(f"fanout inspect: {exc.code}: {exc}", file=sys.stderr)
        return 3 if exc.code == "project_not_found" else 2
    except (LedgerError, sqlite3.Error, OSError, ValueError) as exc:
        print(f"fanout inspect: cannot read ledger: {exc}", file=sys.stderr)
        return 2
    try:
        if args.output is None:
            _write_stdout(content)
        else:
            _check_output_path(args.database, args.output)
            _publish_new_file(args.output, content)
    except (OSError, PreviewError, ValueError) as exc:
        destination_note = "" if args.output is None else f" (output: {args.output})"
        print(f"fanout inspect: cannot write report: {exc}{destination_note}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
