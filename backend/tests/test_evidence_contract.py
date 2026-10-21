import subprocess

import pytest

from harness.evaluators import evaluate_context_freshness, evaluate_unhandled_criteria, evaluate_verification
from harness.models import ContextSnapshot
from harness.repository import HarnessRepository
from test_evaluators import make_task, make_run, criterion
from test_hook_capture import load_capture_module
from test_review_workflow import workflow, complete, review


def test_verification_reasons_survive_repository_restart(tmp_path):
    from test_evaluation_service import setup_service
    service, repository, task, run = setup_service(tmp_path)
    repository.set_run_status(run.run_id, "completed")
    result = service.evaluate_run(task.task_id, run.run_id, {"events": []})
    item = next(item for item in result["evaluations"] if item["evaluator_id"] == "verification")
    assert item.get("reason") == "evidence_missing"
    saved = HarnessRepository(repository.database_path).list_evaluations(task.task_id, run.run_id)
    assert next(item for item in saved if item.evaluator_id == "verification").to_dict()["reason"] == "evidence_missing"


def test_pre_reason_database_migrates_without_rewriting_historical_results(tmp_path):
    from test_evaluation_service import setup_service
    service, repository, task, run = setup_service(tmp_path)
    repository.set_run_status(run.run_id, "completed")
    before = service.evaluate_run(task.task_id, run.run_id, {"events": []})["evaluations"]
    with repository._connect() as connection:
        connection.execute("ALTER TABLE evaluations DROP COLUMN reason")
    migrated = HarnessRepository(repository.database_path)
    after = [item.to_dict() for item in migrated.list_evaluations(task.task_id, run.run_id)]
    assert [{key: value for key, value in item.items() if key != "reason"} for item in after] == [
        {key: value for key, value in item.items() if key != "reason"} for item in before]
    assert all(item["reason"] == "legacy_unspecified" for item in after)


def test_failed_and_unavailable_verification_have_distinct_reasons():
    task = make_task([criterion("command_exit_zero", {"command": "npm test"})])
    failed = evaluate_verification(task, [("failed", "npm test", 1)], make_run())[0]
    unknown = evaluate_verification(task, [("unknown", "npm test", None)], make_run())[0]
    assert failed.to_dict().get("reason") == "verification_failed"
    assert unknown.to_dict().get("reason") == "outcome_unknown"
    manual = evaluate_unhandled_criteria(make_task([criterion("manual", {})]), make_run())[0]
    assert manual.to_dict().get("reason") == "evaluator_unavailable"


@pytest.mark.parametrize("observed,dirty,status,reason", [
    ("a" * 40, False, "passed", "repository_revision_matched"),
    ("b" * 40, False, "failed", "repository_revision_mismatch"),
    ("a" * 40, True, "needs_review", "working_tree_unverified"),
    (None, None, "needs_review", "repository_revision_missing"),
])
def test_snapshot_revision_checked_against_session_start(observed, dirty, status, reason):
    from harness.evaluators import evaluate_repository_revision
    snapshot = ContextSnapshot.from_bundle({"schema_version": "context-bundle/v1", "project": "demo",
        "freshness": "current", "observed_scope": [],
        "repositories": [{"relative_path": "demo", "head_commit": "a" * 40}]}, source="test")
    from harness.models import Run
    run = Run.create(task_id="task-1", context_snapshot_id=snapshot.snapshot_id, cwd="/workspace/demo", status="completed")
    events = [{"event_id": "start", "event_type": "SessionStart", "cwd": "/workspace/demo", "details": {
        "repository_state": {"schema_version": "repository-state/v1", "head_commit": observed,
            "tracked_dirty": dirty, "authority": "client_collected_git", "coverage": "tracked_files_only"}}}]
    result = evaluate_repository_revision(make_task([]), snapshot, run, events)[0]
    assert result.status == status
    assert result.to_dict()["reason"] == reason
    assert snapshot.content["repositories"][0]["head_commit"] == "a" * 40


def test_declared_freshness_does_not_claim_runtime_version_verification():
    snapshot = ContextSnapshot.from_bundle({"freshness": "current", "schema_version": "context-bundle/v1"}, source="test")
    result = evaluate_context_freshness(make_task([]), snapshot, make_run())[0]
    assert result.to_dict().get("reason") == "context_declared_current"


@pytest.mark.parametrize("path,cwd,reason", [
    (".", "/workspace", "repository_revision_mismatch"),
    ("demo", "/workspace/demo/backend", "repository_revision_mismatch"),
    ("demo", "/workspace/Demo", "repository_directory_unverified"),
])
def test_revision_contract_cannot_disappear_for_root_nested_or_unmatched_directory(path, cwd, reason):
    from harness.evaluators import evaluate_repository_revision
    from harness.models import Run
    snapshot = ContextSnapshot.from_bundle({"repositories": [{"relative_path": path, "head_commit": "a" * 40}]}, source="test")
    run = Run.create(task_id="task-1", context_snapshot_id=snapshot.snapshot_id, cwd=cwd)
    events = [{"event_id": "start", "event_type": "SessionStart", "cwd": cwd, "details": {
        "repository_state": {"schema_version": "repository-state/v1", "head_commit": "b" * 40,
            "tracked_dirty": False, "authority": "client_collected_git", "coverage": "tracked_files_only"}}}]
    results = evaluate_repository_revision(make_task([]), snapshot, run, events)
    assert len(results) == 1
    assert results[0].reason == reason


def test_partial_versioned_evaluation_cannot_be_reused_or_accepted(tmp_path):
    from harness.models import TaskContract
    from services.harness_service import HarnessService
    repository = HarnessRepository(tmp_path / "partial.db")
    snapshot = repository.import_context_snapshot({"schema_version": "context-bundle/v1", "freshness": "current",
        "repositories": [{"relative_path": "demo", "head_commit": "a" * 40}]})
    task = repository.create_task(TaskContract.create(title="Synthetic", goal="Review", target_repositories=["demo"],
        constraints=[], acceptance_criteria=[], open_questions=[], risk_level="normal", context_snapshot_id=snapshot.snapshot_id))
    run = repository.create_run(task.task_id, snapshot.snapshot_id, cwd="/workspace/demo")
    repository.set_run_status(run.run_id, "completed")
    item = repository.save_evaluation(evaluate_context_freshness(task, snapshot, run)[0])
    service = HarnessService(repository)
    with pytest.raises(ValueError, match="incomplete evaluation"):
        service.evaluate_run(task.task_id, run.run_id, {"events": []})
    with pytest.raises(ValueError, match="complete evaluation"):
        service.record_review(task.task_id, run.run_id, {"outcome": "accepted", "note": "Synthetic", "evaluation_ids": [item.evaluation_id]})
    assert repository.list_evaluations(task.task_id, run.run_id) == [item]


def test_collector_observes_git_only_at_session_boundaries(tmp_path, monkeypatch):
    module = load_capture_module()
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.test",
                    "commit", "--allow-empty", "-qm", "Synthetic fixture"], check=True)
    sent = []
    monkeypatch.setattr(module, "capture", lambda payload: sent.append(payload))
    module.process_payload({"session_id": "synthetic", "cwd": str(tmp_path), "hook_event_name": "SessionStart"})
    state = sent[-1].get("repository_state", {})
    assert len(state.get("head_commit", "")) == 40
    assert state.get("tracked_dirty") is False
    assert state.get("coverage") == "tracked_files_only"
    module.process_payload({"session_id": "synthetic", "cwd": str(tmp_path), "hook_event_name": "PostToolUse"})
    assert "repository_state" not in sent[-1]
    assert not (tmp_path / ".git" / "index.lock").exists()


def test_repair_comparison_does_not_claim_context_benefit(tmp_path):
    harness, task, audit = workflow(tmp_path)
    before, items = complete(harness, task, audit, "before", 1)
    review(harness, task, before, items, "needs_fix")
    harness.activate_task(task["task_id"], "sample-app")
    after, items = complete(harness, task, audit, "after", 0)
    review(harness, task, after, items, "accepted")
    result = harness.compare_runs(task["task_id"], before["run_id"], after["run_id"])
    assert result.get("comparison_kind") == "repair"
    assert result.get("context_benefit") == "unmeasured"
    assert harness.get_task(task["task_id"])["run_comparisons"] == [result]
