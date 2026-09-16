from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Iterable, Mapping
from uuid import uuid4

TASK_STATUSES = frozenset({"draft", "ready", "active", "evaluating", "needs_review", "needs_fix", "accepted"})
RISK_LEVELS = frozenset({"normal", "high", "destructive"})
FRESHNESS_VALUES = frozenset({"current", "stale", "missing", "unknown"})
RUN_STATUSES = frozenset({"running", "completed", "blocked"})
SCHEMA_VERSION = "context-bundle/v1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("context bundle must contain JSON-compatible values") from exc


def _strings(values: Iterable[str], name: str) -> tuple[str, ...]:
    result = tuple(str(value).strip() for value in values)
    if any(not value for value in result):
        raise ValueError(f"{name} cannot contain empty values")
    return result


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    title: str
    goal: str
    target_repositories: tuple[str, ...]
    constraints: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    open_questions: tuple[str, ...]
    risk_level: str
    status: str
    context_snapshot_id: str | None
    created_at: str

    @classmethod
    def create(cls, *, title: str, goal: str, target_repositories: Iterable[str], constraints: Iterable[str], acceptance_criteria: Iterable[str], open_questions: Iterable[str], risk_level: str, status: str = "draft", context_snapshot_id: str | None = None, task_id: str | None = None, created_at: str | None = None) -> "TaskContract":
        if not title.strip() or not goal.strip():
            raise ValueError("title and goal are required")
        repositories = _strings(target_repositories, "target_repositories")
        if not repositories:
            raise ValueError("target_repositories is required")
        questions = _strings(open_questions, "open_questions")
        if risk_level not in RISK_LEVELS:
            raise ValueError("invalid risk_level")
        if status not in TASK_STATUSES:
            raise ValueError("invalid task status")
        if status == "ready" and questions:
            raise ValueError("a task with open questions cannot be ready")
        return cls(task_id or str(uuid4()), title.strip(), goal.strip(), repositories, _strings(constraints, "constraints"), _strings(acceptance_criteria, "acceptance_criteria"), questions, risk_level, status, context_snapshot_id, created_at or _now())

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "target_repositories": list(self.target_repositories), "constraints": list(self.constraints), "acceptance_criteria": list(self.acceptance_criteria), "open_questions": list(self.open_questions)}


@dataclass(frozen=True)
class ContextSnapshot:
    snapshot_id: str
    schema_version: str
    project: str
    generated_at: str
    freshness: str
    observed_scope: tuple[str, ...]
    content: dict[str, Any]
    content_digest: str
    source: str
    imported_at: str

    @classmethod
    def from_bundle(cls, bundle: Mapping[str, Any], *, source: str, snapshot_id: str | None = None, imported_at: str | None = None) -> "ContextSnapshot":
        if not isinstance(bundle, Mapping):
            raise ValueError("context bundle must be an object")
        canonical = canonical_json(bundle)
        content = json.loads(canonical)
        freshness = str(content.get("freshness", "unknown"))
        if freshness not in FRESHNESS_VALUES:
            raise ValueError("invalid freshness")
        observed_scope = content.get("observed_scope", [])
        if not isinstance(observed_scope, list) or not all(isinstance(item, str) and item.strip() for item in observed_scope):
            raise ValueError("observed_scope must be a list of non-empty strings")
        return cls(snapshot_id or str(uuid4()), str(content.get("schema_version", SCHEMA_VERSION)), str(content.get("project", "")), str(content.get("generated_at", "")), freshness, tuple(observed_scope), content, hashlib.sha256(canonical.encode("utf-8")).hexdigest(), source, imported_at or _now())

    def to_dict(self) -> dict[str, Any]:
        return {"snapshot_id": self.snapshot_id, "schema_version": self.schema_version, "project": self.project, "generated_at": self.generated_at, "freshness": self.freshness, "observed_scope": list(self.observed_scope), "content": self.content, "content_digest": self.content_digest, "source": self.source, "imported_at": self.imported_at}


@dataclass(frozen=True)
class Run:
    run_id: str
    task_id: str
    context_snapshot_id: str
    adapter: str
    session_id: str | None
    cwd: str
    started_at: str
    status: str

    @classmethod
    def create(cls, *, task_id: str, context_snapshot_id: str, adapter: str = "codex-hooks", session_id: str | None = None, cwd: str = "", status: str = "running", run_id: str | None = None, started_at: str | None = None) -> "Run":
        if not task_id or not context_snapshot_id:
            raise ValueError("task_id and context_snapshot_id are required")
        if status not in RUN_STATUSES:
            raise ValueError("invalid run status")
        return cls(run_id or str(uuid4()), task_id, context_snapshot_id, adapter, session_id, cwd, started_at or _now(), status)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
