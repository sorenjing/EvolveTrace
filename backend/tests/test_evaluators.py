from pathlib import Path

from harness.evaluators import evaluate_context_freshness, evaluate_file_exists, evaluate_repository_scope, evaluate_verification
from harness.models import AcceptanceCriterion, ContextSnapshot, Run, TaskContract


def make_task(criteria):
    return TaskContract.create(task_id="task-1", title="x", goal="x", target_repositories=["demo"], constraints=[], acceptance_criteria=criteria, open_questions=[], risk_level="normal")


def make_run():
    return Run.create(task_id="task-1", context_snapshot_id="snapshot-1", run_id="run-1", status="completed")


def criterion(kind, config, required=True, criterion_id="criterion-1"):
    return AcceptanceCriterion.from_payload({"criterion_id": criterion_id, "type": kind, "required": required, "description": "check", "config": config}).to_dict()


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
    assert missing.status == "failed" and missing.evidence_refs == ()
    assert failed.status == "failed" and failed.evidence_refs == ("event-1",)
    assert passed.status == "passed" and passed.evidence_refs == ("event-2",)


def test_file_exists_checks_only_workspace_relative_path(tmp_path: Path):
    (tmp_path / "demo").mkdir()
    (tmp_path / "demo" / "result.txt").write_text("ok")
    task = make_task([criterion("file_exists", {"path": "demo/result.txt"})])
    result = evaluate_file_exists(task, tmp_path, make_run())[0]
    assert result.status == "passed"
