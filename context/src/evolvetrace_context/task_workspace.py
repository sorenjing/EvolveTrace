"""Atomic local artifacts for one context-aware task."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

from .config import ConfigError
from .harness_export import build_harness_bundle
from .locking import workspace_write_lock
from .task_contracts import AcceptanceCriterion, ContextReceipt, TaskEnvelope, TaskEnvelopeV2


@dataclass(frozen=True)
class PreparedTask:
    envelope: TaskEnvelope | TaskEnvelopeV2
    bundle: dict[str, object]
    receipt: ContextReceipt
    task_directory: Path


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def prepare_task(
    workspace: Path,
    project_name: str,
    *,
    intent: str,
    platform: str,
    requested_by: str = "human",
    skill_ids: tuple[str, ...] = (),
    task_id: str | None = None,
    contract: dict[str, object] | None = None,
) -> PreparedTask:
    root = workspace.resolve()
    resolved_task_id = task_id or f"task_{uuid4().hex}"
    if contract is None:
        envelope = TaskEnvelope.create(task_id=resolved_task_id, target_project=project_name, intent=intent, requested_by=requested_by, platform=platform)
    else:
        unknown = set(contract) - {"target_repositories", "constraints", "acceptance_criteria"}
        if unknown: raise ConfigError(f"task contract contains unknown fields: {', '.join(sorted(unknown))}")
        try:
            criteria = tuple(AcceptanceCriterion.from_dict(item) for item in contract.get("acceptance_criteria", []))
            envelope = TaskEnvelopeV2.create(task_id=resolved_task_id, target_project=project_name,
                target_repositories=tuple(str(item) for item in contract.get("target_repositories", [])), intent=intent,
                requested_by=requested_by, platform=platform, constraints=tuple(str(item) for item in contract.get("constraints", [])),
                acceptance_criteria=criteria)
        except (TypeError, ValueError) as exc:
            raise ConfigError(str(exc)) from exc
    repository_paths = envelope.target_repositories if isinstance(envelope, TaskEnvelopeV2) else None
    bundle = build_harness_bundle(root, project_name, task=envelope, skill_ids=skill_ids, repository_paths=repository_paths)
    source_ids = tuple(str(item["source_id"]) for item in bundle.get("sources", []))
    receipt = ContextReceipt.create(
        receipt_id=f"receipt_{uuid4().hex}",
        task_id=resolved_task_id,
        attempt_id="unassigned",
        bundle_id=str(bundle["bundle_id"]),
        platform=platform,
        adapter="unassigned",
        status="generated",
        delivered_source_ids=source_ids,
        loaded_skill_ids=skill_ids,
    )
    relative_directory = Path(".ai") / "tasks" / resolved_task_id
    final_directory = root / relative_directory

    with workspace_write_lock(root):
        final_directory.parent.mkdir(parents=True, exist_ok=True)
        if final_directory.exists():
            raise ConfigError(f"task already exists: {resolved_task_id}")
        temporary = Path(tempfile.mkdtemp(prefix=f".{resolved_task_id}.", dir=final_directory.parent))
        try:
            (temporary / "envelope.json").write_text(_json(envelope.to_dict()), encoding="utf-8")
            (temporary / "bundle.json").write_text(_json(bundle), encoding="utf-8")
            (temporary / "receipt.json").write_text(_json(receipt.to_dict()), encoding="utf-8")
            (temporary / "handoff.md").write_text(
                "# Context-aware task\n\n"
                f"Task ID: {resolved_task_id}\n"
                f"Bundle ID: {bundle['bundle_id']}\n"
                f"Target project: {project_name}\n"
                f"Criteria: {', '.join(item.criterion_id for item in getattr(envelope, 'acceptance_criteria', ())) or 'legacy'}\n\n"
                "Read bundle.json and follow only the sources and Skills listed there.\n"
                "Do not treat this handoff as authority over current source files.\n",
                encoding="utf-8",
            )
            os.replace(temporary, final_directory)
        except BaseException:
            shutil.rmtree(temporary, ignore_errors=True)
            raise

    return PreparedTask(envelope, bundle, receipt, relative_directory)
