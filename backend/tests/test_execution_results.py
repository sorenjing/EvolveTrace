import json

import pytest

from test_activity_attribution import setup, completed, transcript, ingest, by_name


def record(workspace, *, status="Completed", exit_code=0, duration=None):
    value = completed(workspace)
    value["payload"].update(started_at_ms=1767225600000, completed_at_ms=1767225601500)
    value["payload"]["item"].update(status=status, exit_code=exit_code,
                                      duration=duration or {"secs": 1, "nanos": 500000000})
    return value


def test_completed_record_supplies_result_even_when_post_hook_is_missing(setup):
    audit, activity, workspace, home = setup
    path = transcript(home, [record(workspace)])
    ingest(audit, workspace, path, phase="PreToolUse")
    value = by_name(activity)["demo"]["activity"]
    assert value["success_count"] == 1
    assert value["pending_count"] == 0
    assert value["duration_sample_count"] == 1
    assert value["reported_duration_ms"] == 1500
    assert value["result_sources"]["execution_record"] == 1
    assert "exit_code" not in audit.get_session("s-1")["events"][0]["details"]


@pytest.mark.parametrize("status,code,expected", [("Failed", 2, "failed_count"),
                                                 ("Cancelled", None, "cancelled_count"),
                                                 ("Completed", None, "unknown_outcome_count")])
def test_result_states_do_not_infer_success_from_completion(setup, status, code, expected):
    audit, activity, workspace, home = setup
    path = transcript(home, [record(workspace, status=status, exit_code=code)])
    ingest(audit, workspace, path)
    value = by_name(activity)["demo"]["activity"]
    assert value[expected] == 1
    assert value["success_count"] == 0


def test_result_receipt_survives_log_growth_and_restart(setup):
    audit, activity, workspace, home = setup
    path = transcript(home, [record(workspace)])
    ingest(audit, workspace, path)
    first = by_name(activity)["demo"]["activity"]
    assert first["duration_sample_count"] == 1
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "response_item", "payload": {"type": "message", "content": "x" * 1100000}}))
    from services.activity_service import ActivityService
    assert by_name(ActivityService(audit.repository))["demo"]["activity"] == first
    audit.delete_session("s-1")
    with activity.repository._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM activity_execution_results").fetchone()[0] == 0


def test_invalid_numeric_fields_stay_unknown_and_do_not_become_metrics(setup):
    audit, activity, workspace, home = setup
    path = transcript(home, [record(workspace, exit_code=True, duration={"secs": -1, "nanos": 3})])
    ingest(audit, workspace, path)
    value = by_name(activity)["demo"]["activity"]
    assert value["unknown_outcome_count"] == 1
    assert value["duration_sample_count"] == 0


def test_conflicting_hook_and_execution_record_do_not_claim_success(setup):
    audit, activity, workspace, home = setup
    path = transcript(home, [record(workspace)])
    audit.ingest({"event_id": "conflict", "session_id": "s-1", "hook_event_name": "PostToolUse",
                  "cwd": str(workspace), "tool_name": "Bash", "tool_use_id": "call-1", "transcript_path": path,
                  "tool_input": {"command": "npm test"}, "tool_response": {"exit_code": 1}})
    value = by_name(activity)["demo"]["activity"]
    assert value["unknown_outcome_count"] == 1
    assert value["result_sources"]["conflict"] == 1


def test_late_start_event_cannot_overwrite_a_conflicting_result(setup):
    audit, activity, workspace, home = setup
    path = transcript(home, [record(workspace)])
    audit.ingest({"event_id": "conflict-end", "session_id": "s-1", "hook_event_name": "PostToolUse", "sequence": 1,
                  "cwd": str(workspace), "tool_name": "Bash", "tool_use_id": "call-1", "transcript_path": path,
                  "tool_input": {"command": "git status"}, "tool_response": {"exit_code": 1}})
    ingest(audit, workspace, path, phase="PreToolUse")
    value = by_name(activity)["demo"]["activity"]
    assert value["success_count"] == 0
    assert value["result_sources"]["conflict"] == 1


def test_new_result_from_another_directory_cannot_use_old_directory_receipt(setup):
    audit, activity, workspace, home = setup
    changed = record(workspace)
    changed["payload"]["item"]["cwd"] = (workspace / "other").as_uri()
    path = transcript(home, [changed])
    identity = ingest(audit, workspace, path)
    activity.repository.cache_execution_directories([{"event_id": identity, "cwd": str(workspace / "demo"), "_directory_source": "execution_record"}])
    value = by_name(activity)["demo"]["activity"]
    assert value["success_count"] == 0
    assert value["result_sources"]["conflict"] == 1


def test_string_output_is_not_a_structured_exit_code(setup):
    audit, activity, workspace, _ = setup
    audit.ingest({"event_id": "text-output", "session_id": "s-1", "hook_event_name": "PostToolUse",
                  "cwd": str(workspace / "demo"), "tool_name": "Bash",
                  "tool_input": {"command": "npm test"}, "tool_response": '{"exit_code":0}'})
    assert by_name(activity)["demo"]["activity"]["unknown_outcome_count"] == 1


def test_harness_uses_the_same_persisted_results_as_activity(setup):
    from harness.models import TaskContract
    from harness.repository import HarnessRepository
    from services.harness_service import HarnessService
    audit, activity, workspace, home = setup
    path = transcript(home, [record(workspace)])
    ingest(audit, workspace, path, phase="PreToolUse")
    assert by_name(activity)["demo"]["activity"]["success_count"] == 1
    repository = HarnessRepository(home / "harness.db")
    snapshot = repository.import_context_snapshot({"schema_version": "context-bundle/v1", "project": "demo", "freshness": "current", "observed_scope": []})
    task = repository.create_task(TaskContract.create(title="Verify synthetic command", goal="check result", target_repositories=["demo"], constraints=[], open_questions=[], risk_level="normal", context_snapshot_id=snapshot.snapshot_id,
        acceptance_criteria=[{"criterion_id": "verify", "type": "command_exit_zero", "description": "verify", "required": True, "config": {"command": "git status"}}]))
    run = repository.create_run(task.task_id, snapshot.snapshot_id, cwd=str(workspace / "demo"))
    repository.set_run_status(run.run_id, "completed")
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("x" * 1100000)
    result = HarnessService(repository, audit_repository=audit.repository).evaluate_run(task.task_id, run.run_id, audit.get_session("s-1"))
    verification = next(item for item in result["evaluations"] if item["evaluator_id"] == "verification")
    assert verification["status"] == "passed"
    assert verification["evaluator_version"] == "2"
