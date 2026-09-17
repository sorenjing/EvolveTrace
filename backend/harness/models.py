from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Mapping
from uuid import uuid4

from audit.redaction import redact_value

TASK_STATUSES = frozenset({"draft", "ready", "active", "evaluating", "needs_review", "needs_fix", "accepted"})
RISK_LEVELS = frozenset({"normal", "high", "destructive"})
FRESHNESS_VALUES = frozenset({"current", "stale", "missing", "unknown"})
RUN_STATUSES = frozenset({"running", "completed", "blocked"})
DELIVERY_LEVELS = ("generated", "delivered", "acknowledged", "evidenced", "effective")
CRITERION_TYPES = frozenset({"command_exit_zero", "path_scope", "file_exists", "manual"})
EVALUATION_STATUSES = frozenset({"passed", "failed", "needs_review", "skipped"})
EVALUATION_SEVERITIES = frozenset({"info", "warning", "blocking"})
REVIEW_OUTCOMES = frozenset({"accepted", "needs_fix", "blocked"})
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


def _relative_path(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    if not normalized or PurePosixPath(normalized).is_absolute() or PureWindowsPath(value).is_absolute():
        raise ValueError("path must be repository-relative")
    if ".." in PurePosixPath(normalized).parts or "\x00" in normalized:
        raise ValueError("path traversal is not allowed")
    return PurePosixPath(normalized).as_posix()


@dataclass(frozen=True)
class AcceptanceCriterion:
    criterion_id: str
    type: str
    required: bool
    description: str
    config: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "AcceptanceCriterion":
        if set(payload) - {"criterion_id", "type", "required", "description", "config"}:
            raise ValueError("criterion contains unknown fields")
        criterion_id = str(payload.get("criterion_id", "")).strip()
        description = str(payload.get("description", "")).strip()
        kind = str(payload.get("type", ""))
        if not criterion_id or len(criterion_id) > 100 or not description or len(description) > 500:
            raise ValueError("criterion id and description are required and bounded")
        if kind not in CRITERION_TYPES:
            raise ValueError("invalid criterion type")
        config = payload.get("config", {})
        if not isinstance(config, Mapping):
            raise ValueError("criterion config must be an object")
        expected = {"command_exit_zero": {"command"}, "path_scope": {"allowed_prefixes"}, "file_exists": {"path"}, "manual": set()}[kind]
        if set(config) != expected:
            raise ValueError("criterion config keys do not match type")
        clean = dict(config)
        if kind == "command_exit_zero" and not str(clean["command"]).strip():
            raise ValueError("command is required")
        if kind == "file_exists":
            clean["path"] = _relative_path(str(clean["path"]))
        if kind == "path_scope":
            prefixes = clean["allowed_prefixes"]
            if not isinstance(prefixes, list) or not prefixes:
                raise ValueError("allowed_prefixes must be a non-empty list")
            clean["allowed_prefixes"] = [_relative_path(str(item)) for item in prefixes]
        return cls(criterion_id, kind, bool(payload.get("required", False)), description, clean)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskContract:
    task_id: str
    title: str
    goal: str
    target_repositories: tuple[str, ...]
    constraints: tuple[str, ...]
    acceptance_criteria: tuple[str | AcceptanceCriterion, ...]
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
        criteria: list[str | AcceptanceCriterion] = []
        seen: set[str] = set()
        for item in acceptance_criteria:
            if isinstance(item, Mapping):
                criterion = AcceptanceCriterion.from_payload(item)
                if criterion.criterion_id in seen:
                    raise ValueError("duplicate criterion_id")
                seen.add(criterion.criterion_id)
                criteria.append(criterion)
            else:
                value = str(item).strip()
                if not value:
                    raise ValueError("acceptance_criteria cannot contain empty values")
                criteria.append(value)
        return cls(task_id or str(uuid4()), title.strip(), goal.strip(), repositories, _strings(constraints, "constraints"), tuple(criteria), questions, risk_level, status, context_snapshot_id, created_at or _now())

    def to_dict(self) -> dict[str, Any]:
        criteria = [item.to_dict() if isinstance(item, AcceptanceCriterion) else item for item in self.acceptance_criteria]
        return {**asdict(self), "target_repositories": list(self.target_repositories), "constraints": list(self.constraints), "acceptance_criteria": criteria, "open_questions": list(self.open_questions)}


@dataclass(frozen=True)
class EvaluationResult:
    evaluation_id: str
    task_id: str
    run_id: str
    criterion_id: str
    evaluator_id: str
    evaluator_version: str
    status: str
    severity: str
    summary: str
    evidence_refs: tuple[str, ...]
    expected: str
    actual: str
    created_at: str

    @classmethod
    def create(cls, *, task_id: str, run_id: str, criterion_id: str, evaluator_id: str,
               evaluator_version: str, status: str, severity: str, summary: str,
               evidence_refs: Iterable[str], expected: str, actual: str,
               evaluation_id: str | None = None, created_at: str | None = None) -> "EvaluationResult":
        if status not in EVALUATION_STATUSES or severity not in EVALUATION_SEVERITIES:
            raise ValueError("invalid evaluation status or severity")
        if any(not str(value).strip() for value in (task_id, run_id, criterion_id, evaluator_id, evaluator_version, summary)):
            raise ValueError("evaluation identifiers and summary are required")
        return cls(evaluation_id or str(uuid4()), task_id, run_id, criterion_id, evaluator_id,
                   evaluator_version, status, severity, summary, _strings(evidence_refs, "evidence_refs"),
                   expected, actual, created_at or _now())

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "evidence_refs": list(self.evidence_refs)}


@dataclass(frozen=True)
class ReviewDecision:
    decision_id: str
    task_id: str
    run_id: str
    outcome: str
    note: str
    evaluation_ids: tuple[str, ...]
    actor: str
    created_at: str

    @classmethod
    def create(cls, *, task_id: str, run_id: str, outcome: str, note: str,
               evaluation_ids: Iterable[str], actor: str,
               decision_id: str | None = None, created_at: str | None = None) -> "ReviewDecision":
        if outcome not in REVIEW_OUTCOMES:
            raise ValueError("invalid review outcome")
        if not note.strip() or not actor.strip():
            raise ValueError("review note and actor are required")
        return cls(decision_id or str(uuid4()), task_id, run_id, outcome, note.strip(),
                   _strings(evaluation_ids, "evaluation_ids"), actor.strip(), created_at or _now())

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "evaluation_ids": list(self.evaluation_ids)}


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


@dataclass(frozen=True)
class ContextReceipt:
    schema: str
    receipt_id: str
    task_id: str
    context_snapshot_id: str
    attempt_id: str
    bundle_id: str
    platform: str
    adapter: str
    status: str
    delivered_source_ids: tuple[str, ...]
    loaded_skill_ids: tuple[str, ...]
    created_at: str
    updated_at: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ContextReceipt":
        allowed = {
            "schema", "receipt_id", "task_id", "context_snapshot_id", "attempt_id",
            "bundle_id", "platform", "adapter", "status", "delivered_source_ids",
            "loaded_skill_ids", "created_at", "updated_at",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"context receipt contains unknown fields: {', '.join(sorted(unknown))}")
        if redact_value(dict(payload)) != dict(payload):
            raise ValueError("context receipt contains sensitive values")
        if payload.get("schema") != "context-receipt/v1":
            raise ValueError("schema must be context-receipt/v1")
        required = (
            "receipt_id", "task_id", "context_snapshot_id", "attempt_id", "bundle_id",
            "platform", "adapter", "status",
        )
        values = {name: str(payload.get(name, "")).strip() for name in required}
        if any(not value for value in values.values()):
            raise ValueError("context receipt identifiers are required")
        if values["status"] not in DELIVERY_LEVELS:
            raise ValueError("invalid context receipt status")
        sources = _strings(payload.get("delivered_source_ids", []), "delivered_source_ids")
        if values["status"] != "generated" and not sources:
            raise ValueError("delivered_source_ids is required after generation")
        skills = _strings(payload.get("loaded_skill_ids", []), "loaded_skill_ids")
        created_at = str(payload.get("created_at") or _now())
        updated_at = str(payload.get("updated_at") or created_at)
        return cls(
            "context-receipt/v1",
            values["receipt_id"], values["task_id"], values["context_snapshot_id"],
            values["attempt_id"], values["bundle_id"], values["platform"],
            values["adapter"], values["status"], sources, skills, created_at, updated_at,
        )

    def advance(self, status: str, *, attempt_id: str | None = None) -> "ContextReceipt":
        try:
            current = DELIVERY_LEVELS.index(self.status)
            target = DELIVERY_LEVELS.index(status)
        except ValueError as exc:
            raise ValueError("invalid context receipt status") from exc
        if target != current + 1:
            raise ValueError("context receipt must advance exactly one level")
        return ContextReceipt(
            **{
                **asdict(self),
                "attempt_id": attempt_id or self.attempt_id,
                "status": status,
                "updated_at": _now(),
            }
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["delivered_source_ids"] = list(self.delivered_source_ids)
        value["loaded_skill_ids"] = list(self.loaded_skill_ids)
        return value
