"""SQLite dispatch ledger with a fail-closed unknown state."""
from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Iterator

from .plan import Part, Plan, canonical_json

_STATES = {"queued", "dispatching", "running", "outcome_unknown", "completed", "failed"}


class LedgerError(RuntimeError):
    """Raised when a ledger transition is invalid or evidence is incomplete."""


def _require_artifact_reference(reference: Any) -> str:
    """Reject unusable completion receipts without normalizing accepted text."""
    if not isinstance(reference, str) or not str.strip(reference):
        raise LedgerError("completed work needs a non-empty text artifact reference")
    try:
        # Call the built-in encoder, not a str subclass's custom override.
        str.encode(reference, "utf-8")
    except UnicodeEncodeError as exc:
        raise LedgerError("completed work needs a UTF-8 artifact reference") from exc
    # SQLite may adapt a str subclass through __conform__; bind literal text.
    return str.__str__(reference)


class Ledger:
    def __init__(self, database: str = ":memory:") -> None:
        self._db = sqlite3.connect(database, timeout=10, isolation_level=None)
        try:
            self._db.row_factory = sqlite3.Row
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects(
                    project_id TEXT PRIMARY KEY, plan_digest TEXT NOT NULL, plan_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS parts(
                    project_id TEXT NOT NULL, part_id TEXT NOT NULL, payload_json TEXT NOT NULL,
                    payload_digest TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('queued','dispatching','running','outcome_unknown','completed','failed')),
                    worker_id TEXT, task_id TEXT, route_json TEXT, artifact_ref TEXT,
                    evidence_json TEXT, updated_at REAL NOT NULL,
                    PRIMARY KEY(project_id,part_id),
                    FOREIGN KEY(project_id) REFERENCES projects(project_id));
                CREATE TABLE IF NOT EXISTS events(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
                    part_id TEXT, event TEXT NOT NULL, detail_json TEXT NOT NULL, at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS events_project_id ON events(project_id);
                """
            )
        except BaseException:
            self._db.close()
            raise

    @classmethod
    def open_existing(cls, database: str | Path) -> "Ledger":
        """Open an existing regular SQLite file for updates without schema setup.

        The argument is a literal filesystem path. SQLite mode=rw also refuses
        a missing file at connection time; no table or index is created here.
        """
        path = Path(database).absolute()
        if not path.is_file():
            raise LedgerError("database must be an existing regular file")
        ledger = cls.__new__(cls)
        ledger._db = sqlite3.connect(
            path.as_uri() + "?mode=rw", uri=True, timeout=10, isolation_level=None,
        )
        try:
            ledger._db.row_factory = sqlite3.Row
            ledger._db.execute("PRAGMA foreign_keys=ON")
        except BaseException:
            ledger._db.close()
            raise
        return ledger

    @classmethod
    def open_readonly(cls, database: str | Path) -> "Ledger":
        """Open an existing regular SQLite file without initializing its schema.

        The path is a filesystem name, not a caller-supplied SQLite URI. Ordinary
        SQLite locking and WAL visibility apply; no immutable snapshot is assumed.
        """
        path = Path(database).absolute()
        if not path.is_file():
            raise LedgerError("database must be an existing regular file")
        ledger = cls.__new__(cls)
        ledger._db = sqlite3.connect(
            path.as_uri() + "?mode=ro", uri=True, timeout=10, isolation_level=None,
        )
        ledger._db.row_factory = sqlite3.Row
        return ledger

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield self._db
            self._db.commit()
        except BaseException:
            # Cancellation and a failed COMMIT must not leave pending writes
            # that a later connection-context read could accidentally commit.
            self._db.rollback()
            raise

    def _event(self, db: sqlite3.Connection, project_id: str, part_id: str | None,
               event: str, detail: dict[str, Any]) -> None:
        db.execute(
            "INSERT INTO events(project_id,part_id,event,detail_json,at) VALUES(?,?,?,?,?)",
            (project_id, part_id, event, canonical_json(detail), time.time()),
        )

    def record_plan(self, plan: Plan) -> bool:
        # Custom Plan subclasses retain their serialization and key methods.
        # The standard Plan records one native capture, keeping caller-owned
        # mutable Part-like fields paired with their validated identity.
        if type(plan) is Plan:
            captured = Plan(plan.project_id, tuple(
                Part(part.id, part.instruction, part.depends_on, part.tags)
                for part in plan.parts
            ))
            if captured.digest != plan.digest:
                raise LedgerError("plan has changed since validation")
            plan = captured
        document = canonical_json(plan.to_dict())
        with self._transaction() as db:
            prior = db.execute("SELECT plan_digest FROM projects WHERE project_id=?", (plan.project_id,)).fetchone()
            if prior:
                if prior["plan_digest"] != plan.digest:
                    raise LedgerError("project already has a different plan")
                return False
            db.execute("INSERT INTO projects(project_id,plan_digest,plan_json) VALUES(?,?,?)",
                       (plan.project_id, plan.digest, document))
            for part in plan.parts:
                payload = canonical_json(part.to_dict())
                db.execute(
                    "INSERT INTO parts(project_id,part_id,payload_json,payload_digest,idempotency_key,state,updated_at) "
                    "VALUES(?,?,?,?,?,'queued',?)",
                    (plan.project_id, part.id, payload, plan.digest, plan.idempotency_key(part.id), time.time()),
                )
            self._event(db, plan.project_id, None, "plan_recorded", {"part_count": len(plan.parts), "plan_digest": plan.digest})
            return True

    def _part(self, db: sqlite3.Connection, project_id: str, part_id: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM parts WHERE project_id=? AND part_id=?", (project_id, part_id)).fetchone()
        if row is None:
            raise LedgerError("part is not in the ledger")
        return row

    def project_catalog_snapshot(self) -> list[dict[str, Any]]:
        """Read all recorded plan headers in one ordered SQL snapshot.

        This read does not open, commit or roll back a caller's transaction.
        The catalog consumer validates the retained plans before projecting
        their identifiers, digests and authored part counts.
        """
        rows = self._db.execute(
            "SELECT project_id,plan_digest,plan_json FROM projects "
            "ORDER BY project_id COLLATE BINARY"
        ).fetchall()
        return [dict(row) for row in rows]

    def project_snapshot(self, project_id: str) -> dict[str, Any] | None:
        """Read one stored project and its parts in a single SQL snapshot.

        JSON columns remain serialized here. The inspection consumer validates
        them without normalizing recorded identities. Returned rows are detached.
        """
        rows = self._db.execute(
            """
            SELECT 0 AS record_kind, project_id, plan_digest, plan_json,
                   NULL AS part_id, NULL AS payload_json, NULL AS payload_digest,
                   NULL AS idempotency_key, NULL AS state, NULL AS worker_id,
                   NULL AS task_id, NULL AS route_json, NULL AS artifact_ref,
                   NULL AS evidence_json, NULL AS updated_at
            FROM projects WHERE project_id=?
            UNION ALL
            SELECT 1, project_id, NULL, NULL,
                   part_id, payload_json, payload_digest,
                   idempotency_key, state, worker_id,
                   task_id, route_json, artifact_ref, evidence_json, updated_at
            FROM parts WHERE project_id=?
            """,
            (project_id, project_id),
        ).fetchall()
        header = next((row for row in rows if row["record_kind"] == 0), None)
        if header is None:
            return None
        fields = tuple(name for name in header.keys()
                       if name not in ("record_kind", "plan_digest", "plan_json"))
        return {
            "project_id": header["project_id"],
            "plan_digest": header["plan_digest"],
            "plan_json": header["plan_json"],
            "parts": [{name: row[name] for name in fields}
                      for row in rows if row["record_kind"] == 1],
        }

    def project_event_snapshot(self, project_id: str) -> dict[str, Any] | None:
        """Read the stored plan and its ordered event history in one snapshot.

        Keep JSON columns serialized for the history consumer to validate. This
        read neither opens nor commits a caller's transaction.
        """
        rows = self._db.execute(
            """
            SELECT 0 AS record_kind, project_id, plan_digest, plan_json,
                   NULL AS seq, NULL AS part_id, NULL AS event,
                   NULL AS detail_json, NULL AS at
            FROM projects WHERE project_id=?
            UNION ALL
            SELECT 1, project_id, NULL, NULL,
                   seq, part_id, event, detail_json, at
            FROM events WHERE project_id=?
            ORDER BY record_kind, seq
            """,
            (project_id, project_id),
        ).fetchall()
        header = next((row for row in rows if row["record_kind"] == 0), None)
        if header is None:
            return None
        fields = ("seq", "project_id", "part_id", "event", "detail_json", "at")
        return {
            "project_id": header["project_id"],
            "plan_digest": header["plan_digest"],
            "plan_json": header["plan_json"],
            "events": [{name: row[name] for name in fields}
                       for row in rows if row["record_kind"] == 1],
        }

    # A connection context commits or rolls back an active transaction. Reads
    # leave that choice, including any explicit snapshot, with their caller.
    def part_state(self, project_id: str, part_id: str) -> str:
        row = self._db.execute(
            "SELECT state FROM parts WHERE project_id=? AND part_id=?",
            (project_id, part_id),
        ).fetchone()
        if row is None:
            raise LedgerError("part is not in the ledger")
        return row["state"]

    def part(self, project_id: str, part_id: str) -> dict[str, Any]:
        row = self._part(self._db, project_id, part_id)
        result = dict(row)
        for name in ("payload_json", "route_json", "evidence_json"):
            if result.get(name) is not None:
                result[name.removesuffix("_json")] = json.loads(result[name])
        return result

    def idempotency_key(self, project_id: str, part_id: str) -> str:
        return self._part(self._db, project_id, part_id)["idempotency_key"]

    def completed_ids(self, project_id: str) -> set[str]:
        rows = self._db.execute("SELECT part_id FROM parts WHERE project_id=? AND state='completed'", (project_id,))
        return {row[0] for row in rows}

    def dispatchable_ids(self, project_id: str) -> set[str]:
        """Only queued items may be submitted; unknown and in-flight items are excluded."""
        rows = self._db.execute("SELECT part_id FROM parts WHERE project_id=? AND state='queued'", (project_id,))
        return {row[0] for row in rows}

    def withdraw_queued(self, project_id: str, part_id: str, evidence: dict[str, str]) -> None:
        """Record a terminal caller withdrawal before dispatch admission."""
        self._validate_evidence(evidence)
        with self._transaction() as db:
            row = self._part(db, project_id, part_id)
            if row["state"] != "queued":
                raise LedgerError("only queued work may be withdrawn")
            if any(row[name] is not None for name in ("worker_id", "task_id", "route_json", "artifact_ref")):
                raise LedgerError("queued withdrawal requires absent submission and artifact references")
            db.execute("UPDATE parts SET state='failed',evidence_json=?,updated_at=? WHERE project_id=? AND part_id=?",
                       (canonical_json(evidence), time.time(), project_id, part_id))
            self._event(db, project_id, part_id, "queued_withdrawn", evidence)

    def mark_dispatching(self, project_id: str, part_id: str, worker_id: str, route: dict[str, str]) -> None:
        if not isinstance(worker_id, str) or not str.strip(worker_id):
            raise LedgerError("worker id must be non-empty text")
        try:
            str.encode(worker_id, "utf-8")
        except UnicodeEncodeError as exc:
            raise LedgerError("worker id must be UTF-8 text") from exc
        worker_id = str.__str__(worker_id)
        with self._transaction() as db:
            row = self._part(db, project_id, part_id)
            if row["state"] != "queued":
                raise LedgerError("only queued parts may be dispatched")
            db.execute("UPDATE parts SET state='dispatching',worker_id=?,route_json=?,updated_at=? WHERE project_id=? AND part_id=?",
                       (worker_id, canonical_json(route), time.time(), project_id, part_id))
            self._event(db, project_id, part_id, "dispatch_started", {"worker_id": worker_id, "route": route})

    def mark_running(self, project_id: str, part_id: str, task_id: str) -> None:
        if not isinstance(task_id, str) or not str.strip(task_id):
            raise LedgerError("task id must be non-empty text")
        try:
            str.encode(task_id, "utf-8")
        except UnicodeEncodeError as exc:
            raise LedgerError("task id must be UTF-8 text") from exc
        task_id = str.__str__(task_id)
        with self._transaction() as db:
            row = self._part(db, project_id, part_id)
            if row["state"] == "running" and row["task_id"] == task_id:
                return
            if row["state"] != "dispatching":
                raise LedgerError("only a dispatching part may become running")
            db.execute("UPDATE parts SET state='running',task_id=?,updated_at=? WHERE project_id=? AND part_id=?",
                       (task_id, time.time(), project_id, part_id))
            self._event(db, project_id, part_id, "dispatch_accepted", {"task_id": task_id})

    def mark_outcome_unknown(self, project_id: str, part_id: str, evidence: dict[str, str]) -> None:
        self._validate_evidence(evidence)
        with self._transaction() as db:
            row = self._part(db, project_id, part_id)
            if row["state"] == "outcome_unknown":
                return
            if row["state"] not in ("dispatching", "running"):
                raise LedgerError("only an in-flight part may become outcome_unknown")
            db.execute("UPDATE parts SET state='outcome_unknown',evidence_json=?,updated_at=? WHERE project_id=? AND part_id=?",
                       (canonical_json(evidence), time.time(), project_id, part_id))
            self._event(db, project_id, part_id, "outcome_unknown", evidence)

    def mark_completed(self, project_id: str, part_id: str, artifact_ref: str,
                       evidence: dict[str, str] | None = None) -> None:
        artifact_ref = _require_artifact_reference(artifact_ref)
        if evidence is not None:
            self._validate_evidence(evidence)
        with self._transaction() as db:
            row = self._part(db, project_id, part_id)
            if row["state"] != "running":
                raise LedgerError("only running work may complete directly")
            encoded = canonical_json(evidence) if evidence is not None else None
            db.execute("UPDATE parts SET state='completed',artifact_ref=?,evidence_json=?,updated_at=? WHERE project_id=? AND part_id=?",
                       (artifact_ref, encoded, time.time(), project_id, part_id))
            self._event(db, project_id, part_id, "completed", {"artifact_ref": artifact_ref, "evidence": evidence or {}})

    def mark_failed(self, project_id: str, part_id: str, evidence: dict[str, str]) -> None:
        """Record a verified terminal failure of an accepted running task."""
        self._validate_evidence(evidence)
        with self._transaction() as db:
            row = self._part(db, project_id, part_id)
            if row["state"] != "running":
                raise LedgerError("only running work may fail directly")
            db.execute("UPDATE parts SET state='failed',evidence_json=?,updated_at=? WHERE project_id=? AND part_id=?",
                       (canonical_json(evidence), time.time(), project_id, part_id))
            self._event(db, project_id, part_id, "failed", evidence)

    def reconcile_unknown(self, project_id: str, part_id: str, *, verdict: str,
                          evidence: dict[str, str], artifact_ref: str | None = None) -> None:
        if verdict not in ("completed", "failed"):
            raise LedgerError("reconciliation verdict must be completed or failed")
        self._validate_evidence(evidence)
        if verdict == "completed":
            artifact_ref = _require_artifact_reference(artifact_ref)
        with self._transaction() as db:
            row = self._part(db, project_id, part_id)
            if row["state"] != "outcome_unknown":
                raise LedgerError("only outcome_unknown work may be reconciled")
            db.execute("UPDATE parts SET state=?,artifact_ref=?,evidence_json=?,updated_at=? WHERE project_id=? AND part_id=?",
                       (verdict, artifact_ref, canonical_json(evidence), time.time(), project_id, part_id))
            self._event(db, project_id, part_id, "reconciled", {"verdict": verdict, "evidence": evidence, "artifact_ref": artifact_ref})

    def mark_interrupted_dispatches_unknown(self, project_id: str) -> int:
        """Park dispatching rows after restart; never treat them as queued."""
        with self._transaction() as db:
            rows = db.execute("SELECT part_id,idempotency_key FROM parts WHERE project_id=? AND state='dispatching'",
                              (project_id,)).fetchall()
            for row in rows:
                evidence = {"source": "ledger recovery", "locator": row["idempotency_key"],
                            "finding": "process restarted before dispatch acceptance was recorded"}
                db.execute("UPDATE parts SET state='outcome_unknown',evidence_json=?,updated_at=? WHERE project_id=? AND part_id=?",
                           (canonical_json(evidence), time.time(), project_id, row["part_id"]))
                self._event(db, project_id, row["part_id"], "outcome_unknown", evidence)
            return len(rows)

    def events(self, project_id: str, part_id: str | None = None) -> list[dict[str, Any]]:
        if part_id is None:
            rows = self._db.execute("SELECT * FROM events WHERE project_id=? ORDER BY seq", (project_id,)).fetchall()
        else:
            rows = self._db.execute("SELECT * FROM events WHERE project_id=? AND part_id=? ORDER BY seq",
                                    (project_id, part_id)).fetchall()
        return [{**dict(row), "detail": json.loads(row["detail_json"])} for row in rows]

    @staticmethod
    def _validate_evidence(evidence: dict[str, str]) -> None:
        if not isinstance(evidence, dict) or any(not isinstance(evidence.get(key), str) or not evidence[key].strip()
                                                  for key in ("source", "locator", "finding")):
            raise LedgerError("evidence needs non-empty source, locator, and finding")

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "Ledger":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()
