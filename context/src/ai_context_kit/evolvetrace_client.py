"""Optional fail-open submission to a loopback EvolveTrace harness."""

from __future__ import annotations

from dataclasses import dataclass, replace
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .config import ConfigError
from .task_contracts import ContextReceipt, TaskEnvelope, TaskEnvelopeV2


@dataclass(frozen=True)
class SubmissionResult:
    completed: bool
    task_id: str
    snapshot_id: str | None
    receipt_id: str | None
    warning: str | None
    delivered_receipt: ContextReceipt | None = None


def _origin(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "127.0.0.1",
        "::1",
        "localhost",
    }:
        raise ConfigError("EvolveTrace URL must use a loopback host")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigError("EvolveTrace URL must not contain credentials, query, or fragment")
    return value.rstrip("/")


def _post(origin: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        f"{origin}/api{path}",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=3) as response:
        value = json.loads(response.read())
    if not isinstance(value, dict):
        raise ConfigError("EvolveTrace returned an invalid response")
    return value


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
    except HTTPError as exc:
        if 400 <= exc.code < 500:
            raise ConfigError(f"EvolveTrace rejected the submission with HTTP {exc.code}") from exc
        return SubmissionResult(False, envelope.task_id, None, None, "evidence sink unavailable")
    except (URLError, TimeoutError, OSError):
        return SubmissionResult(False, envelope.task_id, None, None, "evidence sink unavailable")
