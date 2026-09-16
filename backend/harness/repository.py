from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import threading
from typing import Any

from .models import ContextSnapshot, Run, TaskContract


class HarnessRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self):
        with self._lock, self._connect() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS context_snapshots (snapshot_id TEXT PRIMARY KEY, schema_version TEXT NOT NULL, project TEXT NOT NULL, generated_at TEXT NOT NULL, freshness TEXT NOT NULL, observed_scope_json TEXT NOT NULL, content_json TEXT NOT NULL, content_digest TEXT UNIQUE NOT NULL, source TEXT NOT NULL, imported_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY, title TEXT NOT NULL, goal TEXT NOT NULL, target_repositories_json TEXT NOT NULL, constraints_json TEXT NOT NULL, acceptance_criteria_json TEXT NOT NULL, open_questions_json TEXT NOT NULL, risk_level TEXT NOT NULL, status TEXT NOT NULL, context_snapshot_id TEXT, created_at TEXT NOT NULL, FOREIGN KEY(context_snapshot_id) REFERENCES context_snapshots(snapshot_id));
                CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, context_snapshot_id TEXT NOT NULL, adapter TEXT NOT NULL, session_id TEXT UNIQUE, cwd TEXT NOT NULL, started_at TEXT NOT NULL, status TEXT NOT NULL, FOREIGN KEY(task_id) REFERENCES tasks(task_id), FOREIGN KEY(context_snapshot_id) REFERENCES context_snapshots(snapshot_id));
                CREATE INDEX IF NOT EXISTS idx_runs_task_started ON runs(task_id, started_at);
                CREATE TABLE IF NOT EXISTS active_task_leases (repository_path TEXT PRIMARY KEY, task_id TEXT NOT NULL, activated_at TEXT NOT NULL, FOREIGN KEY(task_id) REFERENCES tasks(task_id));
                CREATE TABLE IF NOT EXISTS unbound_sessions (session_id TEXT PRIMARY KEY, cwd TEXT NOT NULL, first_seen TEXT NOT NULL);
            """)

    def import_context_snapshot(self, bundle: dict[str, Any], source: str = "file-import") -> ContextSnapshot:
        snapshot = ContextSnapshot.from_bundle(bundle, source=source)
        with self._lock, self._connect() as c:
            row = c.execute("SELECT * FROM context_snapshots WHERE content_digest = ?", (snapshot.content_digest,)).fetchone()
            if row: return self._snapshot(row)
            c.execute("INSERT INTO context_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (snapshot.snapshot_id, snapshot.schema_version, snapshot.project, snapshot.generated_at, snapshot.freshness, json.dumps(snapshot.observed_scope), json.dumps(snapshot.content, ensure_ascii=False, sort_keys=True), snapshot.content_digest, snapshot.source, snapshot.imported_at))
        return snapshot

    def _snapshot(self, row):
        return ContextSnapshot.from_bundle(json.loads(row["content_json"]), source=row["source"], snapshot_id=row["snapshot_id"], imported_at=row["imported_at"])

    def get_context_snapshot(self, snapshot_id):
        with self._lock, self._connect() as c: row = c.execute("SELECT * FROM context_snapshots WHERE snapshot_id=?", (snapshot_id,)).fetchone()
        return self._snapshot(row) if row else None

    def create_task(self, task: TaskContract) -> TaskContract:
        with self._lock, self._connect() as c:
            if task.context_snapshot_id and not c.execute("SELECT 1 FROM context_snapshots WHERE snapshot_id=?", (task.context_snapshot_id,)).fetchone(): raise ValueError("context snapshot does not exist")
            c.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (task.task_id, task.title, task.goal, json.dumps(task.target_repositories), json.dumps(task.constraints), json.dumps(task.acceptance_criteria), json.dumps(task.open_questions), task.risk_level, task.status, task.context_snapshot_id, task.created_at))
        return task

    def _task(self, row):
        return TaskContract.create(task_id=row["task_id"], title=row["title"], goal=row["goal"], target_repositories=json.loads(row["target_repositories_json"]), constraints=json.loads(row["constraints_json"]), acceptance_criteria=json.loads(row["acceptance_criteria_json"]), open_questions=json.loads(row["open_questions_json"]), risk_level=row["risk_level"], status=row["status"], context_snapshot_id=row["context_snapshot_id"], created_at=row["created_at"])

    def get_task(self, task_id):
        with self._lock, self._connect() as c: row = c.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return self._task(row) if row else None

    def list_tasks(self):
        with self._lock, self._connect() as c: rows = c.execute("SELECT * FROM tasks ORDER BY created_at DESC, task_id DESC").fetchall()
        return [self._task(row) for row in rows]

    def create_run(self, task_id, context_snapshot_id, *, adapter="codex-hooks", cwd=""):
        task = self.get_task(task_id)
        if not task: raise ValueError("task does not exist")
        if not self.get_context_snapshot(context_snapshot_id): raise ValueError("context snapshot does not exist")
        if task.context_snapshot_id and task.context_snapshot_id != context_snapshot_id: raise ValueError("run context snapshot must match task")
        run = Run.create(task_id=task_id, context_snapshot_id=context_snapshot_id, adapter=adapter, cwd=cwd)
        with self._lock, self._connect() as c: c.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (run.run_id, run.task_id, run.context_snapshot_id, run.adapter, run.session_id, run.cwd, run.started_at, run.status))
        return run

    def _run(self, row): return Run.create(run_id=row["run_id"], task_id=row["task_id"], context_snapshot_id=row["context_snapshot_id"], adapter=row["adapter"], session_id=row["session_id"], cwd=row["cwd"], started_at=row["started_at"], status=row["status"])
    def get_run(self, run_id):
        with self._lock, self._connect() as c: row = c.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
        return self._run(row) if row else None
    def bind_session(self, run_id, session_id, cwd):
        with self._lock, self._connect() as c:
            row = c.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
            if not row: raise ValueError("run does not exist")
            if row["session_id"] and row["session_id"] != session_id: raise ValueError("run is already bound")
            c.execute("UPDATE runs SET session_id=?, cwd=? WHERE run_id=?", (session_id, cwd, run_id))
            return self._run(c.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())

    def activate_task(self, task_id, repository_path, activated_at):
        task = self.get_task(task_id)
        if not task: raise ValueError("task not found")
        if task.status not in {"ready", "active"}: raise ValueError("only ready tasks can be activated")
        if repository_path not in task.target_repositories: raise ValueError("repository is outside the task scope")
        with self._lock, self._connect() as c:
            c.execute("INSERT OR REPLACE INTO active_task_leases VALUES (?, ?, ?)", (repository_path, task_id, activated_at))
            c.execute("UPDATE tasks SET status='active' WHERE task_id=?", (task_id,))
        return self.get_task(task_id)

    def lease_task(self, repository_path):
        with self._lock, self._connect() as c:
            row = c.execute("SELECT task_id FROM active_task_leases WHERE repository_path=?", (repository_path,)).fetchone()
        return self.get_task(row["task_id"]) if row else None

    def lease_task_for_cwd(self, cwd):
        cwd_parts = tuple(part for part in cwd.replace("\\", "/").split("/") if part and part != ".")
        with self._lock, self._connect() as c:
            leases = c.execute("SELECT repository_path, task_id FROM active_task_leases").fetchall()
        for lease in sorted(leases, key=lambda item: len(tuple(part for part in item["repository_path"].split("/") if part)), reverse=True):
            lease_parts = tuple(part for part in lease["repository_path"].split("/") if part)
            if lease_parts and len(cwd_parts) >= len(lease_parts) and cwd_parts[-len(lease_parts):] == lease_parts:
                return self.get_task(lease["task_id"])
        return None

    def list_runs_for_task(self, task_id):
        with self._lock, self._connect() as c:
            rows = c.execute("SELECT * FROM runs WHERE task_id=? ORDER BY started_at DESC, run_id DESC", (task_id,)).fetchall()
        return [self._run(row) for row in rows]

    def find_run_by_session(self, session_id):
        with self._lock, self._connect() as c: row = c.execute("SELECT * FROM runs WHERE session_id=?", (session_id,)).fetchone()
        return self._run(row) if row else None

    def record_unbound_session(self, session_id, cwd, first_seen):
        with self._lock, self._connect() as c: c.execute("INSERT OR IGNORE INTO unbound_sessions VALUES (?, ?, ?)", (session_id, cwd, first_seen))

    def list_unbound_sessions(self):
        with self._lock, self._connect() as c: rows = c.execute("SELECT * FROM unbound_sessions ORDER BY first_seen DESC, session_id DESC").fetchall()
        return [dict(row) for row in rows]
