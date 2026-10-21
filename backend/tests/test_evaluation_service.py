import pytest

from harness.models import TaskContract
from harness.repository import HarnessRepository
from services.harness_service import HarnessService


def setup_service(tmp_path, criteria=None):
    repository = HarnessRepository(tmp_path / "harness.db")
    snapshot = repository.import_context_snapshot({"schema_version":"context-bundle/v1","project":"demo","generated_at":"2026-09-17T00:00:00+00:00","freshness":"current","observed_scope":["demo"],"repositories":[{"relative_path":"demo"}]})
    task = repository.create_task(TaskContract.create(task_id="task-1", title="x", goal="x", target_repositories=["demo"], constraints=[], acceptance_criteria=criteria if criteria is not None else [
        {"criterion_id":"scope","type":"path_scope","required":True,"description":"scope","config":{"allowed_prefixes":["demo"]}},
        {"criterion_id":"tests","type":"command_exit_zero","required":True,"description":"tests","config":{"command":"python -m pytest -q"}},
    ], open_questions=[], risk_level="normal", status="ready", context_snapshot_id=snapshot.snapshot_id))
    run = repository.create_run(task.task_id, snapshot.snapshot_id)
    return HarnessService(repository), repository, task, run


@pytest.mark.parametrize("kind,config", [("file_exists", {"path": "demo/missing.txt"}), ("manual", {})])
@pytest.mark.parametrize("required", [True, False])
def test_unhandled_criterion_is_visible_and_required_one_blocks_acceptance(tmp_path, kind, config, required):
    service, repository, task, run = setup_service(tmp_path, [{
        "criterion_id": "unhandled", "type": kind, "required": required,
        "description": "Synthetic criterion without an integrated evaluator", "config": config,
    }])
    repository.set_run_status(run.run_id, "completed")
    result = service.evaluate_run(task.task_id, run.run_id, {"events": []})
    item = next(item for item in result["evaluations"] if item["criterion_id"] == "unhandled")
    assert item["status"] == "needs_review"
    assert item["severity"] == ("blocking" if required else "warning")
    assert item["evidence_refs"] == []
    review = {"outcome": "accepted", "note": "Synthetic review", "evaluation_ids": [
        item["evaluation_id"] for item in result["evaluations"]
    ]}
    if required:
        with pytest.raises(ValueError, match="blocking"):
            service.record_review(task.task_id, run.run_id, review)
    else:
        assert service.record_review(task.task_id, run.run_id, review)["outcome"] == "accepted"


@pytest.mark.parametrize("kind,config", [("file_exists", {"path": "demo/missing.txt"}), ("manual", {})])
def test_historical_snapshot_missing_an_unhandled_criterion_cannot_be_accepted(tmp_path, kind, config):
    from harness.evaluators import evaluate_context_freshness

    service, repository, task, run = setup_service(tmp_path, [{
        "criterion_id": "unhandled", "type": kind, "required": True,
        "description": "Synthetic required criterion", "config": config,
    }])
    repository.set_run_status(run.run_id, "completed")
    snapshot = repository.get_context_snapshot(run.context_snapshot_id)
    item = repository.save_evaluation(evaluate_context_freshness(task, snapshot, run)[0])
    with pytest.raises(ValueError, match="complete evaluation"):
        service.record_review(task.task_id, run.run_id, {
            "outcome": "accepted", "note": "Synthetic review", "evaluation_ids": [item.evaluation_id],
        })
    with pytest.raises(ValueError, match="incomplete evaluation"):
        service.evaluate_run(task.task_id, run.run_id, {"events": []})
    assert repository.list_evaluations(task.task_id, run.run_id) == [item]


def test_running_run_cannot_be_evaluated(tmp_path):
    service, _, task, run = setup_service(tmp_path)
    with pytest.raises(ValueError, match="completed or blocked"):
        service.evaluate_run(task.task_id, run.run_id, {"events": []})


def test_acceptance_requires_a_complete_evaluation_snapshot(tmp_path):
    service, repository, task, run = setup_service(tmp_path)
    repository.set_run_status(run.run_id, "completed")
    with pytest.raises(ValueError, match="complete evaluation"):
        service.record_review(task.task_id, run.run_id, {"outcome": "accepted", "note": "missing evaluation", "evaluation_ids": []})


def test_evaluation_persists_results_and_human_decision(tmp_path):
    service, repository, task, run = setup_service(tmp_path)
    repository.set_run_status(run.run_id, "completed")
    session = {"events": [
        {"event_id":"change-1","details":{"changed_files":["demo/app.py"]},"tool_name":"apply_patch"},
        {"event_id":"test-1","details":{"tool_input":{"command":"python -m pytest -q"},"tool_response":{"exit_code":0}},"tool_name":"Bash"},
    ]}
    payload = service.evaluate_run(task.task_id, run.run_id, session)
    assert all(item["status"] == "passed" for item in payload["evaluations"])
    decision = service.record_review(task.task_id, run.run_id, {"outcome":"accepted","note":"reviewed","evaluation_ids":[item["evaluation_id"] for item in payload["evaluations"]],"actor":"human"})
    assert decision["outcome"] == "accepted"


def test_acceptance_is_rejected_when_required_evidence_fails(tmp_path):
    service, repository, task, run = setup_service(tmp_path)
    repository.set_run_status(run.run_id, "completed")
    payload = service.evaluate_run(task.task_id, run.run_id, {"events": []})
    with pytest.raises(ValueError, match="blocking"):
        service.record_review(task.task_id, run.run_id, {"outcome":"accepted","note":"reviewed","evaluation_ids":[item["evaluation_id"] for item in payload["evaluations"]],"actor":"human"})


def test_edit_after_successful_verification_requires_new_verification(tmp_path):
    service, repository, task, run = setup_service(tmp_path)
    repository.set_run_status(run.run_id, "completed")
    events = [
        {"event_id": "pass", "sequence": 1, "tool_name": "Bash", "event_type": "PostToolUse",
         "details": {"tool_input": {"command": "python -m pytest -q"}, "tool_response": {"exit_code": 0}}},
        {"event_id": "edit", "sequence": 2, "tool_name": "apply_patch", "event_type": "PostToolUse",
         "details": {"changed_files": ["demo/app.py"]}},
    ]
    payload = service.evaluate_run(task.task_id, run.run_id, {"events": events})
    verification = next(item for item in payload["evaluations"] if item["evaluator_id"] == "verification")
    assert verification["status"] == "needs_review"
    assert verification["severity"] == "blocking"


def test_test_started_before_edit_is_not_fresh_even_if_it_finishes_after(tmp_path):
    service, repository, task, run = setup_service(tmp_path)
    repository.set_run_status(run.run_id, "completed")
    events = [
        {"event_id": "start", "sequence": 1, "event_type": "PreToolUse", "tool_name": "Bash",
         "details": {"tool_use_id": "c-1", "tool_input": {"command": "python -m pytest -q"}}},
        {"event_id": "edit", "sequence": 2, "event_type": "PostToolUse", "tool_name": "apply_patch",
         "details": {"changed_files": ["demo/app.py"]}},
        {"event_id": "end", "sequence": 3, "event_type": "PostToolUse", "tool_name": "Bash",
         "details": {"tool_use_id": "c-1", "tool_input": {"command": "python -m pytest -q"}, "tool_response": {"exit_code": 0}}},
    ]
    payload = service.evaluate_run(task.task_id, run.run_id, {"events": events})
    verification = next(item for item in payload["evaluations"] if item["evaluator_id"] == "verification")
    assert verification["status"] == "needs_review"


def test_saved_evaluation_snapshot_is_not_changed_by_later_events(tmp_path):
    service, repository, task, run = setup_service(tmp_path)
    repository.set_run_status(run.run_id, "completed")
    first = service.evaluate_run(task.task_id, run.run_id, {"events": []})
    second = service.evaluate_run(task.task_id, run.run_id, {"events": [
        {"event_id": "late", "tool_name": "Bash", "details": {"tool_input": {"command": "python -m pytest -q"}, "tool_response": {"exit_code": 0}}}
    ]})
    assert first == second
