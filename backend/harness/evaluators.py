from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
import posixpath
from typing import Iterable
from uuid import NAMESPACE_URL, uuid5

from audit.activity import command_attempts, ordered_events, _time

from .models import AcceptanceCriterion, ContextSnapshot, EvaluationResult, Run, TaskContract


def _result(task: TaskContract, run: Run, criterion_id: str, evaluator_id: str, *, status: str,
            severity: str, summary: str, evidence_refs: Iterable[str] = (), expected: str = "",
            actual: str = "", version: str = "1") -> EvaluationResult:
    identity = f"{task.task_id}:{run.run_id}:{criterion_id}:{evaluator_id}:{version}"
    return EvaluationResult.create(
        evaluation_id=str(uuid5(NAMESPACE_URL, identity)), task_id=task.task_id, run_id=run.run_id,
        criterion_id=criterion_id, evaluator_id=evaluator_id, evaluator_version=version, status=status,
        severity=severity, summary=summary, evidence_refs=evidence_refs, expected=expected, actual=actual,
    )


def _criteria(task: TaskContract, kind: str):
    return [item for item in task.acceptance_criteria if isinstance(item, AcceptanceCriterion) and item.type == kind]


def _path(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    if not normalized or PurePosixPath(normalized).is_absolute() or PureWindowsPath(value).is_absolute() or ".." in PurePosixPath(normalized).parts or "\x00" in normalized:
        raise ValueError("invalid repository-relative path")
    return PurePosixPath(normalized).as_posix()


def _directory_key(value: str) -> str | None:
    if not value or "\x00" in value:
        return None
    normalized = value.replace("\\", "/")
    if not PureWindowsPath(value).is_absolute() and not PurePosixPath(normalized).is_absolute():
        return None
    normalized = posixpath.normpath(normalized)
    return normalized.casefold() if PureWindowsPath(value).drive else normalized


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


def evaluate_verification(task: TaskContract, command_events: Iterable[tuple[str, str, int | None]], run: Run,
                          *, observed_events: list[dict] | None = None) -> list[EvaluationResult]:
    legacy_order = observed_events is None or all("event_type" not in item for item in observed_events)
    if observed_events is None:
        # Compatibility input is an explicitly ordered list of atomic outcomes.
        observed_events = [{"event_id": identity, "tool_name": "Bash", "cwd": run.cwd,
                            "details": {"tool_input": {"command": command}, "tool_response": {"exit_code": code}}}
                           for identity, command, code in command_events]
    events = ordered_events(observed_events)
    attempts = command_attempts(events)
    edits = [(position, _time(event.get("timestamp")), event["event_id"]) for position, event in enumerate(events)
             if event.get("details", {}).get("changed_files") or event.get("tool_name", "").lower() in {"apply_patch", "edit", "write"}]
    for attempt in attempts:
        if attempt["category"] == "edit":
            edits.append((attempt["end_position"], attempt["time"], attempt["refs"][-1]))
    results = []
    for criterion in _criteria(task, "command_exit_zero"):
        command = str(criterion.config["command"]).strip()
        matches = [attempt for attempt in attempts if attempt["command"].strip() == command
                   and attempt["tool_name"].split(".")[-1].lower() in {"bash", "shell", "exec_command"}]
        severity = "blocking" if criterion.required else "warning"
        status, summary, refs, actual = "needs_review", "Required verification evidence is missing", [], "not observed"
        if not matches:
            pass
        else:
            started = all(item["start_time"] is not None for item in matches)
            ended = all(item["time"] is not None for item in matches)
            clock = "start_time" if started else "time" if ended else "position"
            latest = max(matches, key=lambda item: (item[clock], item["position"]))
            refs, actual = latest["refs"], latest["outcome"]
            root, cwd = _directory_key(run.cwd), _directory_key(latest["cwd"])
            scope_matches = not run.cwd or (root is not None and cwd is not None and (cwd == root or cwd.startswith(root.rstrip("/") + "/")))
            if not scope_matches:
                summary, actual = "Verification directory does not match the run", "directory unverified"
            elif latest["outcome"] == "failure":
                status, summary = "failed", "Latest verification command failed"
            elif latest["outcome"] != "success":
                summary = "Latest verification outcome is not a confirmed success"
            elif len(matches) > 1 and not legacy_order and not (started or ended):
                summary, actual = "Verification ordering is not established", "unknown order"
            else:
                fresh = True
                if edits:
                    if latest["start_time"] is not None and all(time is not None for _, time, _ in edits):
                        fresh = latest["start_time"] > max(time for _, time, _ in edits)
                    else:
                        fresh = latest["start_position"] is not None and latest["start_position"] > max(position for position, _, _ in edits)
                if fresh:
                    status, summary, actual = "passed", "Latest verification succeeded after captured changes", "exit 0"
                else:
                    summary, actual = "Changes require a new verification started afterwards", "verification is stale or ordering is unknown"
                    refs = list(dict.fromkeys([*refs, edits[-1][2]]))
        results.append(_result(task, run, criterion.criterion_id, "verification", status=status, severity=severity, summary=summary, evidence_refs=refs, expected="latest exit 0 after captured changes", actual=actual, version="2"))
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
