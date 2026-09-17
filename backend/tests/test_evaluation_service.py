import pytest

from harness.models import TaskContract
from harness.repository import HarnessRepository
from services.harness_service import HarnessService


def setup_service(tmp_path):
    repository = HarnessRepository(tmp_path / "harness.db")
    snapshot = repository.import_context_snapshot({"schema_version":"context-bundle/v1","project":"demo","generated_at":"2026-09-17T00:00:00+00:00","freshness":"current","observed_scope":["demo"],"repositories":[{"relative_path":"demo"}]})
    task = repository.create_task(TaskContract.create(task_id="task-1", title="x", goal="x", target_repositories=["demo"], constraints=[], acceptance_criteria=[
        {"criterion_id":"scope","type":"path_scope","required":True,"description":"scope","config":{"allowed_prefixes":["demo"]}},
        {"criterion_id":"tests","type":"command_exit_zero","required":True,"description":"tests","config":{"command":"python -m pytest -q"}},
    ], open_questions=[], risk_level="normal", status="ready", context_snapshot_id=snapshot.snapshot_id))
    run = repository.create_run(task.task_id, snapshot.snapshot_id)
    return HarnessService(repository), repository, task, run


def test_running_run_cannot_be_evaluated(tmp_path):
    service, _, task, run = setup_service(tmp_path)
    with pytest.raises(ValueError, match="completed or blocked"):
        service.evaluate_run(task.task_id, run.run_id, {"events": []})


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
