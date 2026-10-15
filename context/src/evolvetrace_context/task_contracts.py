"""Provider-neutral contracts for context-aware tasks."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Literal


DeliveryStatus = Literal[
    "generated", "delivered", "acknowledged", "evidenced", "effective"
]
DELIVERY_LEVELS: tuple[DeliveryStatus, ...] = (
    "generated",
    "delivered",
    "acknowledged",
    "evidenced",
    "effective",
)


def canonical_digest(value: Any) -> str:
    """Return a stable SHA-256 digest for a JSON-compatible value."""

    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _required(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _relative_path(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    if not normalized or PurePosixPath(normalized).is_absolute() or PureWindowsPath(value).is_absolute() or ".." in PurePosixPath(normalized).parts:
        raise ValueError("path must be repository-relative")
    return PurePosixPath(normalized).as_posix()


@dataclass(frozen=True)
class AcceptanceCriterion:
    criterion_id: str
    type: str
    required: bool
    description: str
    config: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AcceptanceCriterion":
        if set(payload) - {"criterion_id", "type", "required", "description", "config"}:
            raise ValueError("criterion contains unknown fields")
        criterion_id = _required(str(payload.get("criterion_id", "")), "criterion_id")
        description = _required(str(payload.get("description", "")), "description")
        if len(criterion_id) > 100 or len(description) > 500:
            raise ValueError("criterion fields exceed length limits")
        kind = str(payload.get("type", ""))
        expected = {"command_exit_zero":{"command"}, "path_scope":{"allowed_prefixes"}, "file_exists":{"path"}, "manual":set()}
        if kind not in expected:
            raise ValueError("invalid criterion type")
        config = payload.get("config", {})
        if not isinstance(config, dict) or set(config) != expected[kind]:
            raise ValueError("criterion config keys do not match type")
        clean = dict(config)
        if kind == "command_exit_zero" and not str(clean["command"]).strip():
            raise ValueError("command is required")
        if kind == "file_exists": clean["path"] = _relative_path(str(clean["path"]))
        if kind == "path_scope":
            if not isinstance(clean["allowed_prefixes"], list) or not clean["allowed_prefixes"]:
                raise ValueError("allowed_prefixes must be a non-empty list")
            clean["allowed_prefixes"] = [_relative_path(str(item)) for item in clean["allowed_prefixes"]]
        return cls(criterion_id, kind, bool(payload.get("required", False)), description, clean)

    def to_dict(self) -> dict[str, Any]: return asdict(self)


@dataclass(frozen=True)
class TaskEnvelope:
    schema: str
    task_id: str
    target_project: str
    intent: str
    requested_by: str
    platform: str
    created_at: str

    @classmethod
    def create(
        cls,
        *,
        task_id: str,
        target_project: str,
        intent: str,
        requested_by: str,
        platform: str,
        created_at: datetime | None = None,
    ) -> TaskEnvelope:
        normalized_intent = _required(intent, "intent")
        if len(normalized_intent) > 500:
            raise ValueError("intent must be at most 500 characters")
        stamp = created_at or datetime.now(timezone.utc)
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("created_at must include a timezone")
        return cls(
            schema="task-envelope/v1",
            task_id=_required(task_id, "task_id"),
            target_project=_required(target_project, "target_project"),
            intent=normalized_intent,
            requested_by=_required(requested_by, "requested_by"),
            platform=_required(platform, "platform"),
            created_at=stamp.isoformat(),
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class TaskEnvelopeV2:
    schema: str
    task_id: str
    target_project: str
    target_repositories: tuple[str, ...]
    intent: str
    requested_by: str
    platform: str
    constraints: tuple[str, ...]
    acceptance_criteria: tuple[AcceptanceCriterion, ...]
    created_at: str

    @classmethod
    def create(cls, *, task_id: str, target_project: str, target_repositories: tuple[str, ...], intent: str,
               requested_by: str, platform: str, constraints: tuple[str, ...], acceptance_criteria: tuple[AcceptanceCriterion, ...],
               created_at: datetime | None = None) -> "TaskEnvelopeV2":
        repositories = tuple(_relative_path(item) for item in target_repositories)
        if not repositories: raise ValueError("target_repositories is required")
        ids = [item.criterion_id for item in acceptance_criteria]
        if len(ids) != len(set(ids)): raise ValueError("duplicate criterion_id")
        stamp = created_at or datetime.now(timezone.utc)
        if stamp.tzinfo is None or stamp.utcoffset() is None: raise ValueError("created_at must include a timezone")
        return cls("task-envelope/v2", _required(task_id, "task_id"), _required(target_project, "target_project"), repositories,
                   _required(intent, "intent"), _required(requested_by, "requested_by"), _required(platform, "platform"),
                   tuple(_required(item, "constraint") for item in constraints), acceptance_criteria, stamp.isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "target_repositories": list(self.target_repositories), "constraints": list(self.constraints), "acceptance_criteria": [item.to_dict() for item in self.acceptance_criteria]}


def task_envelope_from_dict(payload: dict[str, Any]) -> TaskEnvelope | TaskEnvelopeV2:
    if payload.get("schema") == "task-envelope/v1":
        allowed = {"schema","task_id","target_project","intent","requested_by","platform","created_at"}
        if set(payload) != allowed: raise ValueError("v1 task envelope fields are invalid")
        return TaskEnvelope(**payload)
    if payload.get("schema") == "task-envelope/v2":
        allowed = {"schema","task_id","target_project","target_repositories","intent","requested_by","platform","constraints","acceptance_criteria","created_at"}
        if set(payload) != allowed: raise ValueError("v2 task envelope fields are invalid")
        return TaskEnvelopeV2.create(task_id=str(payload["task_id"]), target_project=str(payload["target_project"]), target_repositories=tuple(payload["target_repositories"]), intent=str(payload["intent"]), requested_by=str(payload["requested_by"]), platform=str(payload["platform"]), constraints=tuple(payload["constraints"]), acceptance_criteria=tuple(AcceptanceCriterion.from_dict(item) for item in payload["acceptance_criteria"]), created_at=datetime.fromisoformat(str(payload["created_at"])))
    raise ValueError("unknown task envelope schema")


@dataclass(frozen=True)
class ContextReceipt:
    schema: str
    receipt_id: str
    task_id: str
    attempt_id: str
    bundle_id: str
    platform: str
    adapter: str
    status: DeliveryStatus
    delivered_source_ids: tuple[str, ...]
    loaded_skill_ids: tuple[str, ...]
    execution_profile_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        receipt_id: str,
        task_id: str,
        attempt_id: str,
        bundle_id: str,
        platform: str,
        adapter: str,
        status: DeliveryStatus,
        delivered_source_ids: tuple[str, ...] | list[str],
        loaded_skill_ids: tuple[str, ...] | list[str],
        execution_profile_id: str | None = None,
    ) -> ContextReceipt:
        if status not in ("generated", "delivered"):
            raise ValueError("initial status must be generated or delivered")
        sources = tuple(_required(value, "source identifier") for value in delivered_source_ids)
        if status == "delivered" and not sources:
            raise ValueError("a delivered receipt requires at least one source identifier")
        skills = tuple(_required(value, "skill identifier") for value in loaded_skill_ids)
        return cls(
            schema="context-receipt/v1",
            receipt_id=_required(receipt_id, "receipt_id"),
            task_id=_required(task_id, "task_id"),
            attempt_id=_required(attempt_id, "attempt_id"),
            bundle_id=_required(bundle_id, "bundle_id"),
            platform=_required(platform, "platform"),
            adapter=_required(adapter, "adapter"),
            status=status,
            delivered_source_ids=sources,
            loaded_skill_ids=skills,
            execution_profile_id=(
                _required(execution_profile_id, "execution_profile_id")
                if execution_profile_id is not None else None
            ),
        )

    def advance(self, next_status: DeliveryStatus) -> ContextReceipt:
        try:
            current_index = DELIVERY_LEVELS.index(self.status)
            next_index = DELIVERY_LEVELS.index(next_status)
        except ValueError as exc:
            raise ValueError("unknown delivery status") from exc
        if next_index != current_index + 1:
            raise ValueError("receipt must advance exactly one level")
        return replace(self, status=next_status)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["delivered_source_ids"] = list(self.delivered_source_ids)
        payload["loaded_skill_ids"] = list(self.loaded_skill_ids)
        return payload
