import pytest

from audit.repository import AuditRepository
from harness.repository import HarnessRepository
from services.audit_service import AuditService
from services.harness_service import HarnessService
from test_run_binding import bundle


def workflow(tmp_path):
    harness = HarnessService(HarnessRepository(tmp_path / "harness.db"))
    snapshot = harness.import_context_snapshot(bundle())
    task = harness.create_task({
        "title": "Synthetic repair", "goal": "Verify a corrected run",
        "target_repositories": ["sample-app"], "constraints": [], "open_questions": [],
        "acceptance_criteria": [{"criterion_id": "tests", "type": "command_exit_zero",
            "required": True, "description": "Tests pass", "config": {"command": "npm test"}}],
        "risk_level": "normal", "status": "ready", "context_snapshot_id": snapshot["snapshot_id"],
    })
    harness.ingest_context_receipt({
        "schema": "context-receipt/v1", "receipt_id": "repair-receipt", "task_id": task["task_id"],
        "context_snapshot_id": snapshot["snapshot_id"], "attempt_id": "unassigned", "bundle_id": "synthetic-context",
        "platform": "codex", "adapter": "test", "status": "delivered", "delivered_source_ids": ["context:sample-app"],
    })
    audit = AuditService(AuditRepository(tmp_path / "audit.db"), run_resolver=harness.resolve_or_create_run)
    harness.activate_task(task["task_id"], "sample-app")
    return harness, task, audit


def complete(harness, task, audit, session, exit_code):
    event = {"event_id": session + "-test", "session_id": session, "cwd": "/synthetic/sample-app",
        "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "npm test"},
        "tool_response": {"exit_code": exit_code}}
    run = audit.ingest(event)["run"]
    audit.ingest({"event_id": session + "-stop", "session_id": session, "cwd": "/synthetic/sample-app", "hook_event_name": "Stop"})
    evaluations = harness.evaluate_run(task["task_id"], run["run_id"], audit.get_session(session))["evaluations"]
    return run, evaluations


def review(harness, task, run, evaluations, outcome):
    return harness.record_review(task["task_id"], run["run_id"], {
        "outcome": outcome, "note": "Synthetic human review",
        "evaluation_ids": [item["evaluation_id"] for item in evaluations], "actor": "human",
    })


def test_repair_flow_reuses_contract_and_retains_both_reviews(tmp_path):
    harness, task, audit = workflow(tmp_path)
    original, first = complete(harness, task, audit, "before", 1)
    review(harness, task, original, first, "needs_fix")
    assert harness.activate_task(task["task_id"], "sample-app")["status"] == "active"
    corrected, second = complete(harness, task, audit, "after", 0)
    assert all(item["status"] == "passed" for item in second), second
    review(harness, task, corrected, second, "accepted")
    detail = harness.get_task(task["task_id"])
    assert {run["review_decision"]["outcome"] for run in detail["runs"]} == {"needs_fix", "accepted"}
    assert {run["context_snapshot_id"] for run in detail["runs"]} == {task["context_snapshot_id"]}
    assert detail["acceptance_criteria"] == task["acceptance_criteria"]
    assert harness.repository.list_evaluations(task["task_id"], original["run_id"])[1].status == "failed"
    compared = harness.compare_runs(task["task_id"], original["run_id"], corrected["run_id"])
    assert compared["status"] == "effective"
    reloaded = HarnessService(HarnessRepository(tmp_path / "harness.db"))
    assert reloaded.compare_runs(task["task_id"], original["run_id"], corrected["run_id"]) == compared
    assert reloaded.get_task(task["task_id"])["run_comparisons"] == [compared]
    other = harness.repository.create_run(task["task_id"], task["context_snapshot_id"], cwd="/synthetic/sample-app")
    harness.repository.set_run_status(other.run_id, "completed")
    other_evaluations = harness.evaluate_run(task["task_id"], other.run_id, audit.get_session("before"))["evaluations"]
    review(harness, task, other.to_dict(), other_evaluations, "needs_fix")
    with pytest.raises(ValueError, match="evidenced receipt"):
        harness.compare_runs(task["task_id"], other.run_id, corrected["run_id"])


def test_blocked_review_is_a_readable_persisted_task_state(tmp_path):
    harness, task, audit = workflow(tmp_path)
    run, evaluations = complete(harness, task, audit, "blocked", 1)
    decision = review(harness, task, run, evaluations, "blocked")
    assert decision["outcome"] == "blocked"
    assert harness.get_task(task["task_id"])["status"] == "blocked"
    assert next(item for item in harness.list_tasks() if item["task_id"] == task["task_id"])["status"] == "blocked"


@pytest.mark.parametrize("status", ["needs_review", "needs_fix", "accepted", "blocked"])
def test_inactive_task_lease_does_not_capture_a_new_session(tmp_path, status):
    harness, task, audit = workflow(tmp_path)
    harness.repository.set_task_status(task["task_id"], status)
    event = {"event_id": "unprepared", "session_id": "unprepared", "cwd": "sample-app", "hook_event_name": "PreToolUse"}
    assert audit.ingest(event)["run"] is None
    assert harness.get_task(task["task_id"])["runs"] == []
