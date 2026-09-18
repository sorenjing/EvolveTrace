from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import threading
from typing import Any

from .models import ContextReceipt, ContextSnapshot, DELIVERY_LEVELS, EvaluationResult, ExecutionProfile, ReviewDecision, Run, TaskContract


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
                CREATE TABLE IF NOT EXISTS context_receipts (receipt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, context_snapshot_id TEXT NOT NULL, attempt_id TEXT NOT NULL, bundle_id TEXT NOT NULL, platform TEXT NOT NULL, adapter TEXT NOT NULL, status TEXT NOT NULL, delivered_source_ids_json TEXT NOT NULL, loaded_skill_ids_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, execution_profile_id TEXT, FOREIGN KEY(task_id) REFERENCES tasks(task_id), FOREIGN KEY(context_snapshot_id) REFERENCES context_snapshots(snapshot_id));
                CREATE INDEX IF NOT EXISTS idx_receipts_task_created ON context_receipts(task_id, created_at);
                CREATE TABLE IF NOT EXISTS execution_profiles (profile_id TEXT PRIMARY KEY, profile_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS evaluations (evaluation_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, run_id TEXT NOT NULL, criterion_id TEXT NOT NULL, evaluator_id TEXT NOT NULL, evaluator_version TEXT NOT NULL, status TEXT NOT NULL, severity TEXT NOT NULL, summary TEXT NOT NULL, evidence_refs_json TEXT NOT NULL, expected TEXT NOT NULL, actual TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(task_id, run_id, criterion_id, evaluator_id, evaluator_version), FOREIGN KEY(task_id) REFERENCES tasks(task_id), FOREIGN KEY(run_id) REFERENCES runs(run_id));
                CREATE TABLE IF NOT EXISTS review_decisions (decision_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, run_id TEXT NOT NULL, outcome TEXT NOT NULL, note TEXT NOT NULL, evaluation_ids_json TEXT NOT NULL, actor TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(task_id, run_id), FOREIGN KEY(task_id) REFERENCES tasks(task_id), FOREIGN KEY(run_id) REFERENCES runs(run_id));
            """)
            columns = {
                row["name"] for row in c.execute("PRAGMA table_info(context_receipts)")
            }
            if "execution_profile_id" not in columns:
                c.execute("ALTER TABLE context_receipts ADD COLUMN execution_profile_id TEXT")

    def upsert_execution_profile(self, profile: ExecutionProfile) -> ExecutionProfile:
        rendered = json.dumps(profile.to_dict(), ensure_ascii=False, sort_keys=True)
        with self._lock, self._connect() as c:
            row = c.execute(
                "SELECT profile_json FROM execution_profiles WHERE profile_id=?",
                (profile.profile_id,),
            ).fetchone()
            if row:
                existing = ExecutionProfile.from_payload(json.loads(row["profile_json"]))
                if existing != profile:
                    raise ValueError("execution profile is immutable")
                return existing
            c.execute(
                "INSERT INTO execution_profiles VALUES (?, ?)",
                (profile.profile_id, rendered),
            )
        return profile

    def get_execution_profile(self, profile_id: str) -> ExecutionProfile | None:
        with self._lock, self._connect() as c:
            row = c.execute(
                "SELECT profile_json FROM execution_profiles WHERE profile_id=?",
                (profile_id,),
            ).fetchone()
        return ExecutionProfile.from_payload(json.loads(row["profile_json"])) if row else None

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
            existing_row = c.execute("SELECT * FROM tasks WHERE task_id=?", (task.task_id,)).fetchone()
            if existing_row:
                existing = self._task(existing_row)
                comparable = lambda value: value.to_dict() | {"created_at": None}
                if comparable(existing) != comparable(task):
                    raise ValueError("task_id already exists with different immutable fields")
                return existing
            c.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (task.task_id, task.title, task.goal, json.dumps(task.target_repositories), json.dumps(task.constraints), json.dumps(task.to_dict()["acceptance_criteria"]), json.dumps(task.open_questions), task.risk_level, task.status, task.context_snapshot_id, task.created_at))
        return task

    def _task(self, row):
        return TaskContract.create(task_id=row["task_id"], title=row["title"], goal=row["goal"], target_repositories=json.loads(row["target_repositories_json"]), constraints=json.loads(row["constraints_json"]), acceptance_criteria=json.loads(row["acceptance_criteria_json"]), open_questions=json.loads(row["open_questions_json"]), risk_level=row["risk_level"], status=row["status"], context_snapshot_id=row["context_snapshot_id"], created_at=row["created_at"])

    def get_task(self, task_id):
        with self._lock, self._connect() as c: row = c.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        return self._task(row) if row else None

    def list_tasks(self):
        with self._lock, self._connect() as c: rows = c.execute("SELECT * FROM tasks ORDER BY created_at DESC, task_id DESC").fetchall()
        return [self._task(row) for row in rows]

    def set_task_status(self, task_id: str, status: str):
        with self._lock, self._connect() as c:
            if not c.execute("SELECT 1 FROM tasks WHERE task_id=?", (task_id,)).fetchone():
                raise ValueError("task not found")
            c.execute("UPDATE tasks SET status=? WHERE task_id=?", (status, task_id))
        return self.get_task(task_id)

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
    def set_run_status(self, run_id: str, status: str):
        if status not in {"running", "completed", "blocked"}:
            raise ValueError("invalid run status")
        with self._lock, self._connect() as c:
            if not c.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone():
                raise ValueError("run does not exist")
            c.execute("UPDATE runs SET status=? WHERE run_id=?", (status, run_id))
        return self.get_run(run_id)
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

    def _receipt(self, row) -> ContextReceipt:
        return ContextReceipt.from_payload({
            "schema": "context-receipt/v1",
            "receipt_id": row["receipt_id"],
            "task_id": row["task_id"],
            "context_snapshot_id": row["context_snapshot_id"],
            "attempt_id": row["attempt_id"],
            "bundle_id": row["bundle_id"],
            "platform": row["platform"],
            "adapter": row["adapter"],
            "status": row["status"],
            "delivered_source_ids": json.loads(row["delivered_source_ids_json"]),
            "loaded_skill_ids": json.loads(row["loaded_skill_ids_json"]),
            "execution_profile_id": row["execution_profile_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })

    def upsert_context_receipt(self, receipt: ContextReceipt) -> ContextReceipt:
        with self._lock, self._connect() as c:
            task = c.execute("SELECT context_snapshot_id FROM tasks WHERE task_id=?", (receipt.task_id,)).fetchone()
            if not task:
                raise ValueError("receipt task does not exist")
            if task["context_snapshot_id"] != receipt.context_snapshot_id:
                raise ValueError("receipt context snapshot must match task")
            snapshot = c.execute(
                "SELECT content_json FROM context_snapshots WHERE snapshot_id=?",
                (receipt.context_snapshot_id,),
            ).fetchone()
            snapshot_bundle_id = json.loads(snapshot["content_json"]).get("bundle_id")
            if snapshot_bundle_id is not None and snapshot_bundle_id != receipt.bundle_id:
                raise ValueError("receipt bundle_id must match context snapshot")
            if receipt.execution_profile_id is not None:
                profile = c.execute(
                    "SELECT 1 FROM execution_profiles WHERE profile_id=?",
                    (receipt.execution_profile_id,),
                ).fetchone()
                if profile is None:
                    raise ValueError("execution profile does not exist")
            row = c.execute("SELECT * FROM context_receipts WHERE receipt_id=?", (receipt.receipt_id,)).fetchone()
            if row:
                existing = self._receipt(row)
                immutable = lambda value: (
                    value.receipt_id, value.task_id, value.context_snapshot_id, value.bundle_id,
                    value.platform, value.adapter, value.delivered_source_ids, value.loaded_skill_ids,
                    value.execution_profile_id,
                )
                if immutable(existing) != immutable(receipt):
                    raise ValueError("receipt_id already exists with different immutable fields")
                current = DELIVERY_LEVELS.index(existing.status)
                target = DELIVERY_LEVELS.index(receipt.status)
                if target < current:
                    raise ValueError("context receipt status cannot regress")
                if target > current + 1:
                    raise ValueError("context receipt must advance exactly one level")
                if target == current:
                    if existing.attempt_id != receipt.attempt_id:
                        raise ValueError("receipt attempt cannot change without a status advance")
                    return existing
                c.execute(
                    "UPDATE context_receipts SET attempt_id=?, status=?, updated_at=? WHERE receipt_id=?",
                    (receipt.attempt_id, receipt.status, receipt.updated_at, receipt.receipt_id),
                )
                return receipt
            c.execute(
                "INSERT INTO context_receipts (receipt_id, task_id, context_snapshot_id, attempt_id, bundle_id, platform, adapter, status, delivered_source_ids_json, loaded_skill_ids_json, created_at, updated_at, execution_profile_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    receipt.receipt_id, receipt.task_id, receipt.context_snapshot_id,
                    receipt.attempt_id, receipt.bundle_id, receipt.platform, receipt.adapter,
                    receipt.status, json.dumps(receipt.delivered_source_ids),
                    json.dumps(receipt.loaded_skill_ids), receipt.created_at, receipt.updated_at,
                    receipt.execution_profile_id,
                ),
            )
            return receipt

    def list_context_receipts(self, task_id: str) -> list[ContextReceipt]:
        with self._lock, self._connect() as c:
            rows = c.execute(
                "SELECT * FROM context_receipts WHERE task_id=? ORDER BY created_at, receipt_id",
                (task_id,),
            ).fetchall()
        return [self._receipt(row) for row in rows]

    def acknowledge_delivered_receipt(self, task_id: str, run_id: str) -> ContextReceipt | None:
        receipts = self.list_context_receipts(task_id)
        delivered = next((item for item in reversed(receipts) if item.status == "delivered"), None)
        if delivered is None:
            return None
        return self.upsert_context_receipt(delivered.advance("acknowledged", attempt_id=run_id))

    def _evaluation(self, row) -> EvaluationResult:
        return EvaluationResult.create(
            evaluation_id=row["evaluation_id"], task_id=row["task_id"], run_id=row["run_id"],
            criterion_id=row["criterion_id"], evaluator_id=row["evaluator_id"],
            evaluator_version=row["evaluator_version"], status=row["status"], severity=row["severity"],
            summary=row["summary"], evidence_refs=json.loads(row["evidence_refs_json"]),
            expected=row["expected"], actual=row["actual"], created_at=row["created_at"],
        )

    def save_evaluation(self, result: EvaluationResult) -> EvaluationResult:
        with self._lock, self._connect() as c:
            row = c.execute("SELECT * FROM evaluations WHERE task_id=? AND run_id=? AND criterion_id=? AND evaluator_id=? AND evaluator_version=?", (result.task_id, result.run_id, result.criterion_id, result.evaluator_id, result.evaluator_version)).fetchone()
            if row:
                existing = self._evaluation(row)
                if existing != result:
                    raise ValueError("evaluation already exists with different immutable fields")
                return existing
            c.execute("INSERT INTO evaluations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (result.evaluation_id, result.task_id, result.run_id, result.criterion_id, result.evaluator_id, result.evaluator_version, result.status, result.severity, result.summary, json.dumps(result.evidence_refs), result.expected, result.actual, result.created_at))
        return result

    def list_evaluations(self, task_id: str, run_id: str) -> list[EvaluationResult]:
        with self._lock, self._connect() as c:
            rows = c.execute("SELECT * FROM evaluations WHERE task_id=? AND run_id=? ORDER BY created_at, evaluation_id", (task_id, run_id)).fetchall()
        return [self._evaluation(row) for row in rows]

    def _decision(self, row) -> ReviewDecision:
        return ReviewDecision.create(decision_id=row["decision_id"], task_id=row["task_id"], run_id=row["run_id"], outcome=row["outcome"], note=row["note"], evaluation_ids=json.loads(row["evaluation_ids_json"]), actor=row["actor"], created_at=row["created_at"])

    def save_review_decision(self, decision: ReviewDecision) -> ReviewDecision:
        with self._lock, self._connect() as c:
            row = c.execute("SELECT * FROM review_decisions WHERE task_id=? AND run_id=?", (decision.task_id, decision.run_id)).fetchone()
            if row:
                existing = self._decision(row)
                if existing != decision:
                    raise ValueError("review decision already exists with different immutable fields")
                return existing
            c.execute("INSERT INTO review_decisions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (decision.decision_id, decision.task_id, decision.run_id, decision.outcome, decision.note, json.dumps(decision.evaluation_ids), decision.actor, decision.created_at))
        return decision

    def get_review_decision(self, task_id: str, run_id: str) -> ReviewDecision | None:
        with self._lock, self._connect() as c:
            row = c.execute("SELECT * FROM review_decisions WHERE task_id=? AND run_id=?", (task_id, run_id)).fetchone()
        return self._decision(row) if row else None
