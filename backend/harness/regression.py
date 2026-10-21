"""Portable, data-only regression cases for the existing deterministic evaluators."""

from collections import Counter
import hashlib
import json
from pathlib import PurePosixPath, PureWindowsPath
import re

from .context_bundle import validate_context_bundle
from .evaluators import evaluate_evidence
from .models import ContextSnapshot, EVALUATION_SEVERITIES, EVALUATION_STATUSES, Run, TaskContract


MAX_SUITE_BYTES = 4 * 1024 * 1024
RESULT_FIELDS = {"criterion_id", "evaluator_id", "evaluator_version", "status", "severity", "reason"}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _directory(value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValueError("invalid portable directory")
    path = value.replace("\\", "/")
    if PurePosixPath(path).is_absolute() or PureWindowsPath(path).drive or ".." in PurePosixPath(path).parts:
        raise ValueError("directory must be repository-relative")
    return "/evolvetrace-fixture/" + PurePosixPath(path).as_posix()


def _prepare(case: dict):
    fields = {"schema_version", "case_id", "task", "snapshot", "run", "events", "expected"}
    if not isinstance(case, dict) or set(case) != fields or case["schema_version"] != "regression-case/v1":
        raise ValueError("expected regression-case/v1")
    if not isinstance(case["case_id"], str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", case["case_id"]):
        raise ValueError("invalid case id")
    snapshot = ContextSnapshot.from_bundle(validate_context_bundle(case["snapshot"]), source="regression-case", snapshot_id="frozen-snapshot")
    payload = case["task"]
    if not isinstance(payload, dict):
        raise ValueError("task must be an object")
    for field in ("title", "goal", "risk_level"):
        if not isinstance(payload.get(field), str):
            raise ValueError("task text fields must be strings")
    for field in ("target_repositories", "constraints", "open_questions"):
        if not isinstance(payload.get(field), list) or not all(isinstance(item, str) for item in payload[field]):
            raise ValueError("task list fields must contain strings")
    if not isinstance(payload.get("acceptance_criteria"), list) or not all(isinstance(item, dict) for item in payload["acceptance_criteria"]):
        raise ValueError("regression criteria must be structured")
    task = TaskContract.create(**payload)
    for directory in task.target_repositories:
        _directory(directory)
    if not isinstance(case["run"], dict) or set(case["run"]) != {"cwd"}:
        raise ValueError("run must contain a portable cwd")
    run = Run.create(task_id=task.task_id, context_snapshot_id=snapshot.snapshot_id, run_id="frozen-run",
                     status="completed", cwd=_directory(case["run"]["cwd"]))
    if not isinstance(case["events"], list) or len(case["events"]) > 1000:
        raise ValueError("case supports at most 1000 events")
    events, identities = [], set()
    for raw in case["events"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("details"), dict):
            raise ValueError("event details must be an object")
        identity = raw.get("event_id")
        if not isinstance(identity, str) or not identity or identity in identities:
            raise ValueError("event ids must be present and unique")
        identities.add(identity)
        changed = raw["details"].get("changed_files", [])
        if not isinstance(changed, list) or not all(isinstance(path, str) for path in changed):
            raise ValueError("changed_files must be a list of portable paths")
        for path in changed:
            _directory(path)
        event = {**raw, "session_id": "frozen-session", "cwd": _directory(raw.get("cwd", case["run"]["cwd"]))}
        events.append(event)
    expected = case["expected"]
    if not isinstance(expected, list) or not expected or not all(isinstance(row, dict) and set(row) == RESULT_FIELDS for row in expected):
        raise ValueError("expected must contain complete evaluation signatures")
    if not all(isinstance(value, str) and value for row in expected for value in row.values()):
        raise ValueError("evaluation signatures must contain non-empty strings")
    if any(row["status"] not in EVALUATION_STATUSES or row["severity"] not in EVALUATION_SEVERITIES for row in expected):
        raise ValueError("invalid expected status or severity")
    keys = [(item["criterion_id"], item["evaluator_id"]) for item in expected]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate expected evaluation")
    return task, snapshot, run, events


def replay_suite(suite: dict) -> dict:
    if (not isinstance(suite, dict) or set(suite) != {"schema_version", "evaluator_suite", "cases"}
            or suite["schema_version"] != "regression-suite/v1" or suite["evaluator_suite"] != "evidence/v1"
            or not isinstance(suite["cases"], list) or not 1 <= len(suite["cases"]) <= 100):
        raise ValueError("expected bounded regression-suite/v1 using evidence/v1")
    if len(json.dumps(suite, allow_nan=False).encode()) > MAX_SUITE_BYTES:
        raise ValueError("regression suite exceeds 4 MiB")
    rows, seen = [], set()
    for index, case in enumerate(suite["cases"]):
        record = {"case_id": case.get("case_id", f"case-{index}") if isinstance(case, dict) else f"case-{index}"}
        try:
            task, snapshot, run, events = _prepare(case)
            if case["case_id"] in seen:
                raise ValueError("duplicate case id")
            seen.add(case["case_id"])
            record["input_digest"] = _digest({key: value for key, value in case.items() if key != "expected"})
            record["expected_digest"] = _digest(case["expected"])
        except (ValueError, TypeError, KeyError):
            rows.append({**record, "status": "error", "reason": "invalid_case"})
            continue
        try:
            results = evaluate_evidence(task, snapshot, run, events)
            actual = [{key: item.to_dict()[key] for key in sorted(RESULT_FIELDS)} for item in results]
            order = lambda item: (item["criterion_id"], item["evaluator_id"])
            expected, actual = sorted(case["expected"], key=order), sorted(actual, key=order)
            matched = actual == expected
            counts = Counter(item["status"] for item in actual)
            rows.append({**record, "status": "matched" if matched else "regression",
                         "evaluations": actual, "differences": [] if matched else [{"expected": expected, "actual": actual}],
                         "outcome_counts": {status: counts[status] for status in ("passed", "failed", "needs_review", "skipped")}})
        except Exception as exc:
            rows.append({**record, "status": "error", "reason": "evaluator_error", "error_type": type(exc).__name__})
    counts = Counter(row["status"] for row in rows)
    return {"schema_version": "regression-report/v1", "evaluator_suite": "evidence/v1",
            "claim": "evaluator_consistency_only", "cases": rows,
            "summary": {"total": len(rows), "matched": counts["matched"], "regressions": counts["regression"], "errors": counts["error"]}}
