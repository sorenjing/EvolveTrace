from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness.context_bundle import validate_context_bundle
from harness.evaluators import evaluate_context_freshness, evaluate_repository_scope, evaluate_verification
from harness.models import ContextReceipt, ReviewDecision, TaskContract
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

    def resolve_or_create_run(self, session_id: str, cwd: str, event_type: str | None = None):
        existing = self.repository.find_run_by_session(session_id)
        if existing:
            if event_type in {"Stop", "SessionEnd"} and existing.status == "running":
                existing = self.repository.set_run_status(existing.run_id, "completed")
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

    def evaluate_run(self, task_id: str, run_id: str, session: dict[str, Any] | None):
        task = self.repository.get_task(task_id)
        run = self.repository.get_run(run_id)
        if task is None or run is None or run.task_id != task_id:
            raise ValueError("task or run not found")
        if run.status not in {"completed", "blocked"}:
            raise ValueError("only completed or blocked runs can be evaluated")
        snapshot = self.repository.get_context_snapshot(run.context_snapshot_id)
        changed_paths: list[tuple[str, str]] = []
        command_events: list[tuple[str, str, int]] = []
        for event in (session or {}).get("events", []):
            event_id = str(event.get("event_id", ""))
            details = event.get("details", {})
            for path in details.get("changed_files", []) if isinstance(details, dict) else []:
                changed_paths.append((event_id, str(path)))
            if event.get("tool_name") == "Bash" and isinstance(details, dict):
                tool_input, tool_response = details.get("tool_input", {}), details.get("tool_response", {})
                if isinstance(tool_input, dict) and isinstance(tool_response, dict) and "exit_code" in tool_response:
                    command_events.append((event_id, str(tool_input.get("command", "")), int(tool_response["exit_code"])))
        results = evaluate_context_freshness(task, snapshot, run)
        results += evaluate_repository_scope(task, changed_paths, run)
        results += evaluate_verification(task, command_events, run)
        persisted = [self.repository.save_evaluation(result) for result in results]
        self.repository.set_task_status(task_id, "needs_review")
        receipts = self.repository.list_context_receipts(task_id)
        acknowledged = next((item for item in reversed(receipts) if item.status == "acknowledged"), None)
        required_ids = {item.criterion_id for item in task.acceptance_criteria if hasattr(item, "criterion_id") and item.required}
        evidenced_ids = {item.criterion_id for item in persisted if item.evidence_refs}
        if acknowledged is not None and required_ids <= evidenced_ids:
            self.repository.upsert_context_receipt(acknowledged.advance("evidenced", attempt_id=run_id))
        return {"task_id": task_id, "run_id": run_id, "evaluations": [item.to_dict() for item in persisted]}

    def record_review(self, task_id: str, run_id: str, payload: dict[str, Any]):
        results = self.repository.list_evaluations(task_id, run_id)
        requested = tuple(str(item) for item in payload.get("evaluation_ids", []))
        if set(requested) != {item.evaluation_id for item in results}:
            raise ValueError("review must reference the current evaluation set")
        outcome = str(payload.get("outcome", ""))
        if outcome == "accepted" and any(item.status != "passed" and item.severity == "blocking" for item in results):
            raise ValueError("blocking evaluations prevent acceptance")
        decision = ReviewDecision.create(task_id=task_id, run_id=run_id, outcome=outcome,
            note=str(payload.get("note", "")), evaluation_ids=requested, actor=str(payload.get("actor", "human")))
        saved = self.repository.save_review_decision(decision)
        self.repository.set_task_status(task_id, outcome)
        return saved.to_dict()

    def compare_runs(self, task_id: str, original_run_id: str, corrected_run_id: str):
        if original_run_id == corrected_run_id:
            raise ValueError("comparison requires two different runs")
        original = self.repository.get_run(original_run_id)
        corrected = self.repository.get_run(corrected_run_id)
        if original is None or corrected is None or original.task_id != task_id or corrected.task_id != task_id:
            raise ValueError("comparison runs must belong to the task")
        original_decision = self.repository.get_review_decision(task_id, original_run_id)
        corrected_decision = self.repository.get_review_decision(task_id, corrected_run_id)
        if original_decision is None or original_decision.outcome != "needs_fix":
            raise ValueError("original run must have a needs_fix decision")
        if corrected_decision is None or corrected_decision.outcome != "accepted":
            raise ValueError("corrected run must have an accepted decision")
        original_criteria = {(item.criterion_id, item.type, json.dumps(item.config, sort_keys=True)) for item in self.repository.get_task(task_id).acceptance_criteria if hasattr(item, "criterion_id")}
        corrected_results = self.repository.list_evaluations(task_id, corrected_run_id)
        if {item.criterion_id for item in corrected_results} - {"context-freshness"} != {item[0] for item in original_criteria}:
            raise ValueError("corrected run does not cover the same criterion set")
        receipts = self.repository.list_context_receipts(task_id)
        evidenced = next((item for item in reversed(receipts) if item.status == "evidenced"), None)
        if evidenced is None:
            raise ValueError("comparison requires an evidenced receipt")
        effective = self.repository.upsert_context_receipt(evidenced.advance("effective", attempt_id=corrected_run_id))
        return {"task_id": task_id, "original_run_id": original_run_id, "corrected_run_id": corrected_run_id, "status": effective.status, "receipt_id": effective.receipt_id}
