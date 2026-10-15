from pathlib import Path

import pytest

from harness.evaluators import evaluate_context_freshness, evaluate_file_exists, evaluate_repository_scope, evaluate_verification
from harness.models import AcceptanceCriterion, ContextSnapshot, Run, TaskContract


def make_task(criteria):
    return TaskContract.create(task_id="task-1", title="x", goal="x", target_repositories=["demo"], constraints=[], acceptance_criteria=criteria, open_questions=[], risk_level="normal")


def make_run():
    return Run.create(task_id="task-1", context_snapshot_id="snapshot-1", run_id="run-1", status="completed")


def criterion(kind, config, required=True, criterion_id="criterion-1"):
    return AcceptanceCriterion.from_payload({"criterion_id": criterion_id, "type": kind, "required": required, "description": "check", "config": config}).to_dict()


def test_latest_verification_failure_overrides_earlier_success():
    task = make_task([criterion("command_exit_zero", {"command": "npm test"})])
    result = evaluate_verification(task, [("old-pass", "npm test", 0), ("new-fail", "npm test", 1)], make_run())[0]
    assert result.status == "failed"
    assert result.evidence_refs == ("new-fail",)
    assert result.evaluator_version == "2"


def test_unknown_latest_verification_never_reuses_earlier_success():
    task = make_task([criterion("command_exit_zero", {"command": "npm test"})])
    result = evaluate_verification(task, [("old-pass", "npm test", 0), ("new-unknown", "npm test", None)], make_run())[0]
    assert result.status == "needs_review"


def test_matching_command_in_another_repository_is_not_verification():
    task = make_task([criterion("command_exit_zero", {"command": "npm test"})])
    run = Run.create(task_id="task-1", context_snapshot_id="snapshot-1", status="completed", cwd="/workspace/demo")
    events = [{"event_id": "other-repo", "cwd": "/workspace/other", "tool_name": "Bash",
               "details": {"tool_input": {"command": "npm test"}, "tool_response": {"exit_code": 0}}}]
    assert evaluate_verification(task, [], run, observed_events=events)[0].status == "needs_review"


@pytest.mark.parametrize("cwd", ["/workspace/demo/../other", "workspace/demo"])
def test_uncanonical_or_relative_directory_does_not_pass_verification(cwd):
    task = make_task([criterion("command_exit_zero", {"command": "npm test"})])
    run = Run.create(task_id="task-1", context_snapshot_id="snapshot-1", status="completed", cwd="/workspace/demo")
    events = [{"event_id": "wrong-directory", "cwd": cwd, "tool_name": "Bash",
               "details": {"tool_input": {"command": "npm test"}, "tool_response": {"exit_code": 0}}}]
    assert evaluate_verification(task, [], run, observed_events=events)[0].status == "needs_review"


def test_replayed_old_success_cannot_override_newer_failed_completion():
    task = make_task([criterion("command_exit_zero", {"command": "npm test"})])
    events = [{"event_id": identity, "event_type": "PostToolUse", "sequence": sequence,
               "timestamp": timestamp, "tool_name": "Bash", "details": {
                   "tool_input": {"command": "npm test"}, "tool_response": {"exit_code": code}}}
              for identity, sequence, timestamp, code in [
                  ("new-failure", 1, "2026-01-01T00:02:00+00:00", 1),
                  ("replayed-old-success", 2, "2026-01-01T00:01:00+00:00", 0)]]
    result = evaluate_verification(task, [], make_run(), observed_events=events)[0]
    assert result.status == "failed"
    assert result.evidence_refs == ("new-failure",)


def test_context_freshness_fails_stale_snapshot():
    snapshot = ContextSnapshot.from_bundle({"schema_version": "context-bundle/v1", "project": "demo", "freshness": "stale", "observed_scope": []}, source="test", snapshot_id="snapshot-1")
    result = evaluate_context_freshness(make_task([]), snapshot, make_run())[0]
    assert (result.status, result.severity) == ("failed", "blocking")


def test_repository_scope_rejects_unexpected_path():
    task = make_task([criterion("path_scope", {"allowed_prefixes": ["demo/src"]})])
    result = evaluate_repository_scope(task, [("event-1", "other/secret.py")], make_run())[0]
    assert result.status == "failed"
    assert result.evidence_refs == ("event-1",)


def test_verification_distinguishes_missing_failed_and_passed_evidence():
    task = make_task([criterion("command_exit_zero", {"command": "python -m pytest -q"})])
    missing = evaluate_verification(task, [], make_run())[0]
    failed = evaluate_verification(task, [("event-1", "python -m pytest -q", 1)], make_run())[0]
    passed = evaluate_verification(task, [("event-2", "python -m pytest -q", 0)], make_run())[0]
    assert missing.status == "needs_review" and missing.evidence_refs == ()
    assert failed.status == "failed" and failed.evidence_refs == ("event-1",)
    assert passed.status == "passed" and passed.evidence_refs == ("event-2",)


def test_file_exists_checks_only_workspace_relative_path(tmp_path: Path):
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "result.txt").write_text("ok")
    task = make_task([criterion("file_exists", {"path": "demo/result.txt"})])
    result = evaluate_file_exists(task, tmp_path, make_run())[0]
    assert result.status == "passed"
