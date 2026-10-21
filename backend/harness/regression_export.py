"""Minimal local evidence drafts; human labels remain separate from scoring."""

import copy
import json
import math
from pathlib import PurePosixPath, PureWindowsPath
import posixpath

from .context_bundle import _contains_absolute_path
from .evaluators import evaluate_evidence
from .regression import MAX_SUITE_BYTES, RESULT_FIELDS, _digest, _prepare


def _typed_fields(source: dict, fields: tuple[str, ...]) -> dict:
    nullable = type(None)
    text = (str,)
    numbers = (int, float, nullable)
    types = {"exit_code": (int, nullable), "status": (str, nullable), "duration_ms": numbers,
             "command": text, "cmd": text, "schema_version": text, "authority": text, "coverage": text,
             "head_commit": (str, nullable), "tracked_dirty": (bool, nullable), "event_type": text,
             "tool_name": text, "sequence": (int, nullable), "timestamp": (str, nullable),
             "outcome": text, "started_at": numbers, "completed_at": numbers, "conflict": (bool,)}
    result = {}
    for key in fields:
        if key not in source:
            continue
        value = source[key]
        if type(value) not in types[key] or (isinstance(value, float) and not math.isfinite(value)):
            raise ValueError("export requires typed scalar evidence fields")
        result[key] = value
    return result


def _relative_directory(value: object, root: str) -> str:
    if not isinstance(value, str) or not value or "\x00" in value or not isinstance(root, str) or not root or "\x00" in root:
        raise ValueError("an observed directory and absolute workspace root are required")
    windows = bool(PureWindowsPath(root).drive)
    path_type = PureWindowsPath if windows else PurePosixPath
    base = path_type(posixpath.normpath(root.replace("\\", "/")))
    path = path_type(posixpath.normpath(value.replace("\\", "/")))
    if not base.is_absolute() or not path.is_absolute() or ".." in path.parts:
        raise ValueError("directories must be absolute and within the selected workspace")
    try:
        return path.relative_to(base).as_posix()
    except ValueError as exc:
        raise ValueError("directory lies outside the selected workspace; prepare a case manually") from exc


def _signatures(results):
    return sorted(({key: item.to_dict()[key] for key in sorted(RESULT_FIELDS)} for item in results),
                  key=lambda row: (row["criterion_id"], row["evaluator_id"]))


def build_draft(task, snapshot, run, events: list[dict], *, workspace_root: str, case_id: str) -> dict:
    if not isinstance(events, list) or len(events) > 1000:
        raise ValueError("export supports at most 1000 events; no events were truncated")
    case = {"schema_version": "regression-case/v1", "case_id": case_id,
            "task": {"title": "Local evidence case", "goal": "Review frozen execution evidence",
                     "target_repositories": list(task.target_repositories), "constraints": [], "open_questions": [],
                     "risk_level": task.risk_level, "acceptance_criteria": task.to_dict()["acceptance_criteria"]},
            "snapshot": {"schema_version": snapshot.schema_version, "project": "local-case",
                         "generated_at": snapshot.generated_at, "freshness": snapshot.freshness,
                         "observed_scope": [], "context": {}, "repositories": [
                             {key: item[key] for key in ("relative_path", "head_commit") if key in item}
                             for item in snapshot.content.get("repositories", [])]},
            "run": {"cwd": _relative_directory(run.cwd, workspace_root)}, "events": [], "expected": []}
    calls = {}
    for index, event in enumerate(events):
        details = event.get("details", {})
        if not isinstance(details, dict):
            raise ValueError("event details must be structured")
        # Omit body-specific fields; recorded commands can still contain private inline code.
        clean = _typed_fields(details, ("exit_code", "status", "duration_ms"))
        if "changed_files" in details:
            paths = details["changed_files"]
            if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
                raise ValueError("export requires typed changed-file paths")
            clean["changed_files"] = list(paths)
        tool_input = details.get("tool_input")
        if isinstance(tool_input, dict):
            clean["tool_input"] = _typed_fields(tool_input, ("command", "cmd"))
        elif isinstance(tool_input, str) and event.get("tool_name", "").split(".")[-1].lower() in {"bash", "shell", "exec_command"}:
            clean["tool_input"] = tool_input
        response = details.get("tool_response")
        if isinstance(response, dict):
            clean["tool_response"] = _typed_fields(response, ("exit_code", "status", "duration_ms"))
        if details.get("tool_use_id"):
            identity = str(details["tool_use_id"])
            clean["tool_use_id"] = calls.setdefault(identity, f"call-{len(calls) + 1}")
        if isinstance(details.get("safety"), dict) and details["safety"].get("decision") == "deny":
            clean["safety"] = {"decision": "deny"}
        if isinstance(details.get("repository_state"), dict):
            clean["repository_state"] = _typed_fields(details["repository_state"],
                ("schema_version", "authority", "coverage", "head_commit", "tracked_dirty"))
        projected = _typed_fields(event, ("event_type", "tool_name", "sequence", "timestamp"))
        projected.update(event_id=f"event-{index + 1}", cwd=_relative_directory(event.get("cwd"), workspace_root), details=clean)
        if isinstance(event.get("_execution_result"), dict):
            projected["_execution_result"] = _typed_fields(event["_execution_result"],
                ("outcome", "exit_code", "duration_ms", "started_at", "completed_at", "conflict"))
        case["events"].append(projected)
    if len(json.dumps(case).encode()) > MAX_SUITE_BYTES:
        raise ValueError("draft exceeds 4 MiB; no data was truncated")
    if _contains_absolute_path(case):
        raise ValueError("case contains absolute path-like text; prepare a portable case manually")
    original = _signatures(evaluate_evidence(task, snapshot, run, events))
    probe = {**case, "expected": original}
    portable_task, portable_snapshot, portable_run, portable_events = _prepare(probe)
    if _signatures(evaluate_evidence(portable_task, portable_snapshot, portable_run, portable_events)) != original:
        raise ValueError("projection changes evaluation semantics; prepare a case manually")
    draft = {"schema_version": "regression-draft/v1", "source": {"run_id": run.run_id,
             "snapshot_digest": snapshot.content_digest, "event_count": len(events)},
             "input_digest": _digest({key: value for key, value in case.items() if key != "expected"}),
             "review": {"status": "pending", "reviewer": "", "basis": ""}, "case": case}
    if len(json.dumps(draft).encode()) > MAX_SUITE_BYTES:
        raise ValueError("draft exceeds 4 MiB; no data was truncated")
    return draft


def freeze_draft(draft: dict) -> dict:
    fields = {"schema_version", "source", "input_digest", "review", "case"}
    if not isinstance(draft, dict) or set(draft) != fields or draft["schema_version"] != "regression-draft/v1":
        raise ValueError("expected regression-draft/v1")
    review = draft["review"]
    if (not isinstance(review, dict) or set(review) != {"status", "reviewer", "basis"} or review["status"] != "confirmed"
            or not all(isinstance(review[key], str) and 1 <= len(review[key].strip()) <= 1000 for key in ("reviewer", "basis"))):
        raise ValueError("confirm independent human review, reviewer and evidence basis first")
    case = draft["case"]
    if not isinstance(case, dict) or _digest({key: value for key, value in case.items() if key != "expected"}) != draft["input_digest"]:
        raise ValueError("input digest changed; export and review the input again")
    if _contains_absolute_path(case):
        raise ValueError("case must not contain absolute path-like text")
    _prepare(case)  # Validate the human labels; agreement with the evaluator is NOT required.
    suite = {"schema_version": "regression-suite/v1", "evaluator_suite": "evidence/v1", "cases": [copy.deepcopy(case)]}
    if len(json.dumps(suite).encode()) > MAX_SUITE_BYTES:
        raise ValueError("suite exceeds 4 MiB")
    return suite
