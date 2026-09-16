from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.context_bundle import validate_context_bundle
from harness.models import ContextReceipt, TaskContract
from harness.repository import HarnessRepository


def _default_path() -> Path:
    return Path(os.getenv("EVOLVETRACE_HARNESS_DB_PATH", Path(tempfile.gettempdir()) / "evolvetrace" / "harness.db"))


class HarnessService:
    def __init__(self, repository: HarnessRepository | None = None):
        self.repository = repository or HarnessRepository(_default_path())

    def import_context_snapshot(self, payload: dict[str, Any], source: str = "file-import"):
        return self.repository.import_context_snapshot(validate_context_bundle(payload), source=source).to_dict()

    def create_task(self, payload: dict[str, Any]):
        fields = {key: payload.get(key, []) for key in ("target_repositories", "constraints", "acceptance_criteria", "open_questions")}
        task = TaskContract.create(task_id=payload.get("task_id"), title=str(payload.get("title", "")), goal=str(payload.get("goal", "")), risk_level=str(payload.get("risk_level", "normal")), status=str(payload.get("status", "draft")), context_snapshot_id=payload.get("context_snapshot_id"), **fields)
        return self.repository.create_task(task).to_dict()

    def list_tasks(self):
        return [task.to_dict() for task in self.repository.list_tasks()]

    def get_task(self, task_id: str):
        task = self.repository.get_task(task_id)
        if task is None:
            return None
        value = task.to_dict()
        value["context_snapshot"] = self.repository.get_context_snapshot(task.context_snapshot_id).to_dict() if task.context_snapshot_id else None
        value["runs"] = [run.to_dict() for run in self.repository.list_runs_for_task(task.task_id)]
        value["context_receipts"] = [receipt.to_dict() for receipt in self.repository.list_context_receipts(task.task_id)]
        return value

    def ingest_context_receipt(self, payload: dict[str, Any]):
        return self.repository.upsert_context_receipt(ContextReceipt.from_payload(payload)).to_dict()

    def list_context_receipts(self, task_id: str):
        if self.repository.get_task(task_id) is None:
            raise ValueError("task not found")
        return [receipt.to_dict() for receipt in self.repository.list_context_receipts(task_id)]

    @staticmethod
    def _repository_key(path: str) -> str:
        value = path.replace("\\", "/").strip("/")
        return "/".join(part for part in value.split("/") if part not in {"", "."})

    def activate_task(self, task_id: str, repository_path: str):
        key = self._repository_key(repository_path)
        return self.repository.activate_task(task_id, key, datetime.now(timezone.utc).isoformat()).to_dict()

    def resolve_or_create_run(self, session_id: str, cwd: str):
        existing = self.repository.find_run_by_session(session_id)
        if existing:
            return existing.to_dict()
        key = self._repository_key(cwd)
        task = self.repository.lease_task_for_cwd(key)
        if task is None:
            self.repository.record_unbound_session(session_id, cwd, datetime.now(timezone.utc).isoformat())
            return None
        if task.context_snapshot_id is None:
            return None
        run = self.repository.create_run(task.task_id, task.context_snapshot_id, cwd=key)
        bound = self.repository.bind_session(run.run_id, session_id, key)
        self.repository.acknowledge_delivered_receipt(task.task_id, bound.run_id)
        return bound.to_dict()

    def list_unbound_runs(self):
        return self.repository.list_unbound_sessions()
