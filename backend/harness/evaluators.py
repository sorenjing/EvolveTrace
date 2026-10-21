from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
import posixpath
import re
from typing import Iterable
from uuid import NAMESPACE_URL, uuid5

from audit.activity import command_attempts, ordered_events, _time

from .models import AcceptanceCriterion, ContextSnapshot, EvaluationResult, Run, TaskContract


def _result(task: TaskContract, run: Run, criterion_id: str, evaluator_id: str, *, status: str,
            severity: str, summary: str, evidence_refs: Iterable[str] = (), expected: str = "",
            actual: str = "", version: str = "1", reason: str = "legacy_unspecified") -> EvaluationResult:
    identity = f"{task.task_id}:{run.run_id}:{criterion_id}:{evaluator_id}:{version}"
    return EvaluationResult.create(
        evaluation_id=str(uuid5(NAMESPACE_URL, identity)), task_id=task.task_id, run_id=run.run_id,
        criterion_id=criterion_id, evaluator_id=evaluator_id, evaluator_version=version, status=status,
        severity=severity, summary=summary, evidence_refs=evidence_refs, expected=expected, actual=actual, reason=reason,
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
        status, severity, summary = "passed", "blocking", "Context was declared current at export; this does not verify runtime repository state"
        reason = "context_declared_current"
    elif snapshot.freshness == "unknown":
        status, severity, summary = "needs_review", "warning", "Context freshness is unknown"
        reason = "context_freshness_unknown"
    else:
        status, severity, summary = "failed", "blocking", "Context snapshot is stale, missing, or incompatible"
        reason = "context_not_current"
    return [_result(task, run, "context-freshness", "context-freshness", status=status, severity=severity, summary=summary, evidence_refs=[snapshot.snapshot_id], expected="current context-bundle/v1", actual=f"{snapshot.freshness} {snapshot.schema_version}", reason=reason)]


def has_repository_revision(snapshot: ContextSnapshot) -> bool:
    return any(isinstance(item, dict) and isinstance(item.get("head_commit"), str)
               and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", item["head_commit"])
               for item in snapshot.content.get("repositories", []))


def evaluate_repository_revision(task: TaskContract, snapshot: ContextSnapshot, run: Run, events: list[dict]) -> list[EvaluationResult]:
    if not has_repository_revision(snapshot):
        return []  # Historical bundles without a pinned revision remain readable.
    root = _directory_key(run.cwd)
    repositories = snapshot.content.get("repositories", [])
    candidates = []
    for item in repositories:
        if not isinstance(item, dict) or not isinstance(item.get("relative_path"), str) or not root:
            continue
        relative = posixpath.normpath(item["relative_path"].replace("\\", "/"))
        if PureWindowsPath(run.cwd).drive:
            relative = relative.casefold()
        marker = "/" + relative
        if (relative == "." and len(repositories) == 1) or root.endswith(marker) or marker + "/" in root:
            candidates.append(item)
    repository = max(candidates, key=lambda item: len(item["relative_path"])) if candidates else {}
    expected = repository.get("head_commit")
    if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", expected):
        return [_result(task, run, "repository-revision", "repository-revision", status="needs_review", severity="warning",
                        reason="repository_directory_unverified", summary="Run directory cannot be mapped to a pinned repository",
                        evidence_refs=[snapshot.snapshot_id], expected="a pinned repository revision", actual="directory unverified")]
    starts = [event for event in ordered_events(events) if event.get("event_type") == "SessionStart"
              and _directory_key(event.get("cwd", "")) == root]
    event = starts[0] if starts else {}
    state = event.get("details", {}).get("repository_state", {})
    observed = state.get("head_commit") if isinstance(state, dict) else None
    known = (isinstance(state, dict) and state.get("schema_version") == "repository-state/v1"
             and state.get("authority") == "client_collected_git" and state.get("coverage") == "tracked_files_only"
             and isinstance(observed, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", observed))
    if not known:
        status, severity, reason, summary = "needs_review", "warning", "repository_revision_missing", "Session-start repository revision was not observed"
    elif observed != expected:
        status, severity, reason, summary = "failed", "blocking", "repository_revision_mismatch", "Session started from a different revision than the context snapshot"
    elif state.get("tracked_dirty") is not False:
        status, severity, reason, summary = "needs_review", "warning", "working_tree_unverified", "Commit matches, but tracked working-tree contents are not verified"
    else:
        status, severity, reason, summary = "passed", "info", "repository_revision_matched", "Session-start commit matches; untracked files and semantic freshness remain unverified"
    return [_result(task, run, "repository-revision", "repository-revision", status=status, severity=severity,
                    reason=reason, summary=summary, expected=expected, actual=observed if known else "not observed",
                    evidence_refs=[snapshot.snapshot_id, *([event["event_id"]] if event else [])])]


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
            reason = "evidence_missing"
        elif outside:
            status, severity, summary = "failed", "blocking", "Changed paths exceed the declared scope"
            reason = "scope_mismatch"
        else:
            status, severity, summary = "passed", "blocking", "All changed paths are within scope"
            reason = "scope_matched"
        results.append(_result(task, run, criterion.criterion_id, "repository-scope", status=status, severity=severity, summary=summary, evidence_refs=evidence, expected=", ".join(allowed), actual=", ".join(outside) if outside else "within scope", reason=reason))
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
        reason = "evidence_missing"
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
                reason = "directory_unverified"
            elif latest["outcome"] == "failure":
                status, summary = "failed", "Latest verification command failed"
                reason = "verification_failed"
            elif latest["outcome"] != "success":
                summary = "Latest verification outcome is not a confirmed success"
                reason = "outcome_unknown"
            elif len(matches) > 1 and not legacy_order and not (started or ended):
                summary, actual = "Verification ordering is not established", "unknown order"
                reason = "ordering_unknown"
            else:
                fresh = True
                if edits:
                    if latest["start_time"] is not None and all(time is not None for _, time, _ in edits):
                        fresh = latest["start_time"] > max(time for _, time, _ in edits)
                    else:
                        fresh = latest["start_position"] is not None and latest["start_position"] > max(position for position, _, _ in edits)
                if fresh:
                    status, summary, actual = "passed", "Latest verification succeeded after captured changes", "exit 0"
                    reason = "verification_succeeded"
                else:
                    summary, actual = "Changes require a new verification started afterwards", "verification is stale or ordering is unknown"
                    reason = "verification_stale"
                    refs = list(dict.fromkeys([*refs, edits[-1][2]]))
        results.append(_result(task, run, criterion.criterion_id, "verification", status=status, severity=severity, summary=summary, evidence_refs=refs, expected="latest exit 0 after captured changes", actual=actual, version="2", reason=reason))
    return results


def evaluate_unhandled_criteria(task: TaskContract, run: Run) -> list[EvaluationResult]:
    # File checks need a trusted workspace; manual criteria need explicit evidence.
    # Neither is integrated into the service yet, so do not imply either passed.
    return [
        _result(task, run, criterion.criterion_id, "unhandled-criterion",
                status="needs_review", severity="blocking" if criterion.required else "warning",
                summary=f"Criterion requires an evaluator not integrated into this run: {criterion.type}",
                expected=criterion.description, actual="not evaluated", reason="evaluator_unavailable")
        for criterion in task.acceptance_criteria
        if isinstance(criterion, AcceptanceCriterion) and criterion.type in {"file_exists", "manual"}
    ]


def evaluate_evidence(task: TaskContract, snapshot: ContextSnapshot, run: Run, events: list[dict]) -> list[EvaluationResult]:
    """Pure evaluator entrypoint shared by live review and offline regression."""
    changed = [(event["event_id"], str(path)) for event in events
               for path in event.get("details", {}).get("changed_files", [])]
    return (evaluate_context_freshness(task, snapshot, run)
            + evaluate_repository_revision(task, snapshot, run, events)
            + evaluate_repository_scope(task, changed, run)
            + evaluate_verification(task, [], run, observed_events=events)
            + evaluate_unhandled_criteria(task, run))
