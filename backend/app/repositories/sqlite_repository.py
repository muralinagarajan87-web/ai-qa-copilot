from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from backend.app.domain.workflow_run import WorkflowRun

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class SqliteWorkflowRunRepository:
    """SQLite is sufficient for a single-user local tool; WorkflowRun is
    stored as a JSON blob keyed by run_id rather than normalized into
    columns, since the Orchestrator is the only writer and always
    round-trips the whole entity. A lock serializes writes across the
    threadpool FastAPI uses for sync endpoints.
    """

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(_SCHEMA)
            self._conn.commit()

    def create(self, run: WorkflowRun) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO workflow_runs (run_id, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (run.run_id, run.model_dump_json(), run.created_at.isoformat(), run.updated_at.isoformat()),
            )
            self._conn.commit()

    def get(self, run_id: str) -> WorkflowRun | None:
        with self._lock:
            row = self._conn.execute("SELECT data FROM workflow_runs WHERE run_id = ?", (run_id,)).fetchone()
        return WorkflowRun.model_validate_json(row[0]) if row else None

    def update(self, run: WorkflowRun) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE workflow_runs SET data = ?, updated_at = ? WHERE run_id = ?",
                (run.model_dump_json(), run.updated_at.isoformat(), run.run_id),
            )
            self._conn.commit()

    def list(self) -> list[WorkflowRun]:
        with self._lock:
            rows = self._conn.execute("SELECT data FROM workflow_runs ORDER BY created_at DESC").fetchall()
        return [WorkflowRun.model_validate_json(row[0]) for row in rows]
