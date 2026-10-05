"""SQLite dispatch ledger with a fail-closed unknown state."""
from __future__ import annotations

from contextlib import contextmanager
import json
import sqlite3
import time
from typing import Any, Iterator

from .plan import Plan, canonical_json

_STATES = {"queued", "dispatching", "running", "outcome_unknown", "completed", "failed"}


class LedgerError(RuntimeError):
    """Raised when a ledger transition is invalid or evidence is incomplete."""


class Ledger:
    def __init__(self, database: str = ":memory:") -> None:
        self._db = sqlite3.connect(database, timeout=10, isolation_level=None)
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
            """
        )

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        self._db.execute("BEGIN IMMEDIATE")
        try:
            yield self._db
        except Exception:
            self._db.rollback()
            raise
        else:
            self._db.commit()

    def _event(self, db: sqlite3.Connection, project_id: str, part_id: str | None,
               event: str, detail: dict[str, Any]) -> None:
        db.execute(
            "INSERT INTO events(project_id,part_id,event,detail_json,at) VALUES(?,?,?,?,?)",
            (project_id, part_id, event, canonical_json(detail), time.time()),
        )

    def record_plan(self, plan: Plan) -> bool:
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

    def part_state(self, project_id: str, part_id: str) -> str:
        with self._db:
            return self._part(self._db, project_id, part_id)["state"]

    def part(self, project_id: str, part_id: str) -> dict[str, Any]:
        with self._db:
            row = self._part(self._db, project_id, part_id)
            result = dict(row)
            for name in ("payload_json", "route_json", "evidence_json"):
                if result.get(name) is not None:
                    result[name.removesuffix("_json")] = json.loads(result[name])
            return result

    def idempotency_key(self, project_id: str, part_id: str) -> str:
        with self._db:
            return self._part(self._db, project_id, part_id)["idempotency_key"]

    def completed_ids(self, project_id: str) -> set[str]:
        with self._db:
            rows = self._db.execute("SELECT part_id FROM parts WHERE project_id=? AND state='completed'", (project_id,))
            return {row[0] for row in rows}

    def dispatchable_ids(self, project_id: str) -> set[str]:
        """Only queued items may be submitted; unknown and in-flight items are excluded."""
        with self._db:
            rows = self._db.execute("SELECT part_id FROM parts WHERE project_id=? AND state='queued'", (project_id,))
            return {row[0] for row in rows}

    def mark_dispatching(self, project_id: str, part_id: str, worker_id: str, route: dict[str, str]) -> None:
        if not worker_id:
            raise LedgerError("worker id is required")
        with self._transaction() as db:
            row = self._part(db, project_id, part_id)
            if row["state"] != "queued":
                raise LedgerError("only queued parts may be dispatched")
            db.execute("UPDATE parts SET state='dispatching',worker_id=?,route_json=?,updated_at=? WHERE project_id=? AND part_id=?",
                       (worker_id, canonical_json(route), time.time(), project_id, part_id))
            self._event(db, project_id, part_id, "dispatch_started", {"worker_id": worker_id, "route": route})

    def mark_running(self, project_id: str, part_id: str, task_id: str) -> None:
        if not task_id:
            raise LedgerError("task id is required")
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
        if not artifact_ref:
            raise LedgerError("completed work needs an artifact reference")
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

    def reconcile_unknown(self, project_id: str, part_id: str, *, verdict: str,
                          evidence: dict[str, str], artifact_ref: str | None = None) -> None:
        if verdict not in ("completed", "failed"):
            raise LedgerError("reconciliation verdict must be completed or failed")
        self._validate_evidence(evidence)
        if verdict == "completed" and not artifact_ref:
            raise LedgerError("completed reconciliation needs an artifact reference")
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
        with self._db:
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
