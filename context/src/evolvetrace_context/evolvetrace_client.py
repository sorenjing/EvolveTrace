"""Optional fail-open submission to a loopback EvolveTrace harness."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .config import ConfigError
from .local_transport import LocalHTTPError, LocalServiceUnavailable, _origin, request_json
from .task_contracts import ContextReceipt, TaskEnvelope, TaskEnvelopeV2


@dataclass(frozen=True)
class SubmissionResult:
    completed: bool
    task_id: str
    snapshot_id: str | None
    receipt_id: str | None
    warning: str | None
    delivered_receipt: ContextReceipt | None = None


def _post(origin: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    return request_json(origin, "POST", path, payload)


def build_task_payload(envelope: TaskEnvelope | TaskEnvelopeV2, snapshot_id: str, repository_paths: list[str]) -> dict[str, Any]:
    if isinstance(envelope, TaskEnvelopeV2):
        if list(envelope.target_repositories) != repository_paths:
            raise ConfigError("task repositories must match the context bundle")
        constraints = list(envelope.constraints)
        criteria = [item.to_dict() for item in envelope.acceptance_criteria]
        repositories = list(envelope.target_repositories)
    else:
        constraints = ["Use only the task-bound context sources"]
        criteria = ["Produce deterministic verification evidence"]
        repositories = repository_paths
    return {"task_id": envelope.task_id, "title": envelope.intent, "goal": envelope.intent,
            "target_repositories": repositories, "constraints": constraints,
            "acceptance_criteria": criteria, "open_questions": [], "risk_level": "normal",
            "status": "ready", "context_snapshot_id": snapshot_id}


def submit_task(
    base_url: str,
    *,
    envelope: TaskEnvelope | TaskEnvelopeV2,
    bundle: dict[str, Any],
    receipt: ContextReceipt,
) -> SubmissionResult:
    origin = _origin(base_url)
    try:
        snapshot = _post(origin, "/harness/context-snapshots", bundle)
        snapshot_id = str(snapshot.get("snapshot_id", ""))
        if not snapshot_id:
            raise ConfigError("EvolveTrace response omitted snapshot_id")
        repositories = bundle.get("repositories", [])
        repository_paths = [str(item["relative_path"]) for item in repositories]
        task = _post(origin, "/harness/tasks", build_task_payload(envelope, snapshot_id, repository_paths))
        task_id = str(task.get("task_id", ""))
        if task_id != envelope.task_id:
            raise ConfigError("EvolveTrace returned a mismatched task_id")
        delivered = replace(receipt, status="delivered", adapter="evolvetrace-http")
        receipt_payload = delivered.to_dict()
        receipt_payload["context_snapshot_id"] = snapshot_id
        receipt_response = _post(origin, "/harness/context-receipts", receipt_payload)
        receipt_id = str(receipt_response.get("receipt_id", ""))
        if receipt_id != receipt.receipt_id:
            raise ConfigError("EvolveTrace returned a mismatched receipt_id")
        repository_path = repository_paths[0] if repository_paths else envelope.target_project
        _post(
            origin,
            f"/harness/tasks/{task_id}/activate",
            {"repository_path": repository_path},
        )
        return SubmissionResult(True, task_id, snapshot_id, receipt_id, None, delivered)
    except LocalHTTPError as exc:
        if 400 <= exc.code < 500:
            raise ConfigError(f"EvolveTrace rejected the submission with HTTP {exc.code}") from exc
        return SubmissionResult(False, envelope.task_id, None, None, "evidence sink unavailable")
    except LocalServiceUnavailable:
        return SubmissionResult(False, envelope.task_id, None, None, "evidence sink unavailable")
