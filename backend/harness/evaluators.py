from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable
from uuid import NAMESPACE_URL, uuid5

from .models import AcceptanceCriterion, ContextSnapshot, EvaluationResult, Run, TaskContract


def _result(task: TaskContract, run: Run, criterion_id: str, evaluator_id: str, *, status: str,
            severity: str, summary: str, evidence_refs: Iterable[str] = (), expected: str = "",
            actual: str = "") -> EvaluationResult:
    identity = f"{task.task_id}:{run.run_id}:{criterion_id}:{evaluator_id}:1"
    return EvaluationResult.create(
        evaluation_id=str(uuid5(NAMESPACE_URL, identity)), task_id=task.task_id, run_id=run.run_id,
        criterion_id=criterion_id, evaluator_id=evaluator_id, evaluator_version="1", status=status,
        severity=severity, summary=summary, evidence_refs=evidence_refs, expected=expected, actual=actual,
    )


def _criteria(task: TaskContract, kind: str):
    return [item for item in task.acceptance_criteria if isinstance(item, AcceptanceCriterion) and item.type == kind]


def _path(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    if not normalized or PurePosixPath(normalized).is_absolute() or PureWindowsPath(value).is_absolute() or ".." in PurePosixPath(normalized).parts or "\x00" in normalized:
        raise ValueError("invalid repository-relative path")
    return PurePosixPath(normalized).as_posix()


def evaluate_context_freshness(task: TaskContract, snapshot: ContextSnapshot, run: Run) -> list[EvaluationResult]:
    if snapshot.freshness == "current" and snapshot.schema_version == "context-bundle/v1":
        status, severity, summary = "passed", "blocking", "Context snapshot is current"
    elif snapshot.freshness == "unknown":
        status, severity, summary = "needs_review", "warning", "Context freshness is unknown"
    else:
        status, severity, summary = "failed", "blocking", "Context snapshot is stale, missing, or incompatible"
    return [_result(task, run, "context-freshness", "context-freshness", status=status, severity=severity, summary=summary, evidence_refs=[snapshot.snapshot_id], expected="current context-bundle/v1", actual=f"{snapshot.freshness} {snapshot.schema_version}")]


def evaluate_repository_scope(task: TaskContract, changed_paths: Iterable[tuple[str, str]], run: Run) -> list[EvaluationResult]:
    results = []
    for criterion in _criteria(task, "path_scope"):
        allowed = tuple(_path(value).rstrip("/") for value in criterion.config["allowed_prefixes"])
        evidence, outside = [], []
        for event_id, raw_path in changed_paths:
            try:
                path = _path(raw_path)
            except ValueError:
                path = raw_path
            evidence.append(event_id)
            if not any(path == prefix or path.startswith(prefix + "/") for prefix in allowed):
                outside.append(path)
        if not evidence:
            status, severity, summary = "needs_review", "blocking" if criterion.required else "warning", "No changed-file evidence was captured"
        elif outside:
            status, severity, summary = "failed", "blocking", "Changed paths exceed the declared scope"
        else:
            status, severity, summary = "passed", "blocking", "All changed paths are within scope"
        results.append(_result(task, run, criterion.criterion_id, "repository-scope", status=status, severity=severity, summary=summary, evidence_refs=evidence, expected=", ".join(allowed), actual=", ".join(outside) if outside else "within scope"))
    return results


def evaluate_verification(task: TaskContract, command_events: Iterable[tuple[str, str, int]], run: Run) -> list[EvaluationResult]:
    events = list(command_events)
    results = []
    for criterion in _criteria(task, "command_exit_zero"):
        command = str(criterion.config["command"]).strip()
        matches = [(event_id, exit_code) for event_id, observed, exit_code in events if observed.strip() == command]
        if not matches:
            status, severity, summary, refs, actual = "failed" if criterion.required else "needs_review", "blocking" if criterion.required else "warning", "Required verification evidence is missing", [], "not observed"
        elif any(code == 0 for _, code in matches):
            status, severity, summary, refs, actual = "passed", "blocking", "Verification command succeeded", [event_id for event_id, code in matches if code == 0], "exit 0"
        else:
            status, severity, summary, refs, actual = "failed", "blocking", "Verification command failed", [event_id for event_id, _ in matches], f"exit {matches[-1][1]}"
        results.append(_result(task, run, criterion.criterion_id, "verification", status=status, severity=severity, summary=summary, evidence_refs=refs, expected="exit 0", actual=actual))
    return results


def evaluate_file_exists(task: TaskContract, workspace_root: Path, run: Run) -> list[EvaluationResult]:
    results = []
    root = workspace_root.resolve()
    for criterion in _criteria(task, "file_exists"):
        relative = _path(str(criterion.config["path"]))
        target = (root / relative).resolve()
        inside = target == root or root in target.parents
        exists = inside and target.is_file()
        status = "passed" if exists else "failed" if criterion.required else "needs_review"
        severity = "blocking" if criterion.required else "warning"
        results.append(_result(task, run, criterion.criterion_id, "file-exists", status=status, severity=severity, summary="Required file exists" if exists else "Required file is missing", evidence_refs=[f"path:{relative}"] if exists else [], expected=relative, actual="exists" if exists else "missing"))
    return results
