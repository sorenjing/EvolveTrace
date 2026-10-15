import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit.repository import AuditRepository
from services.activity_service import ActivityService
from services.audit_service import AuditService


def setup(tmp_path, monkeypatch):
    home = tmp_path / "codex"
    (home / "sessions").mkdir(parents=True)
    monkeypatch.setenv("CODEX_HOME", str(home))
    audit = AuditService(AuditRepository(tmp_path / "audit.db"))
    activity = ActivityService(audit.repository)
    path = home / "sessions/synthetic.jsonl"
    path.write_text(json.dumps({"type": "session_meta", "payload": {"id": "synthetic"}}) + "\n")
    return audit, activity, path


def ingest(audit, path, identity="one"):
    return audit.ingest({"event_id": identity, "session_id": "synthetic", "hook_event_name": "PreToolUse",
                         "tool_name": "Bash", "tool_use_id": identity, "transcript_path": str(path),
                         "tool_input": {"command": "npm test"}})["event"]["event_id"]


def complete(path, identity="one"):
    with path.open("a") as handle:
        handle.write(json.dumps({"type": "event_msg", "payload": {"type": "item_completed", "thread_id": "synthetic",
            "item": {"type": "CommandExecution", "id": identity, "cwd": path.parent.as_uri(),
                     "status": "Completed", "exit_code": 0, "duration": {"secs": 2, "nanos": 0},
                     "aggregated_output": "Synthetic private output"}}}) + "\n")


def test_worker_retries_late_results_without_report_queries_and_survives_restart(tmp_path, monkeypatch):
    audit, activity, path = setup(tmp_path, monkeypatch)
    ref = ingest(audit, path)
    worker = activity.evidence_worker
    worker.tick(now=100)
    assert activity.repository.execution_results([ref]) == {}
    complete(path)
    # The persisted retry schedule prevents a restart from causing a hot loop.
    restarted = ActivityService(audit.repository).evidence_worker
    assert restarted.tick(now=101)["attempted"] == 0
    assert restarted.tick(now=500)["resolved"] == 1
    result = activity.repository.execution_results([ref])[ref]
    assert result["outcome"] == "success"
    assert result["duration_ms"] == 2000
    assert "Synthetic private output" not in str(result)
    assert audit.get_session("synthetic")["events"][0]["cwd"] == ""
    assert restarted.tick(now=900)["attempted"] == 0
    audit.delete_session("synthetic")
    assert restarted.tick(now=1000)["pending"] == 0


def test_bounded_batches_do_not_starve_newer_events(tmp_path, monkeypatch):
    audit, activity, path = setup(tmp_path, monkeypatch)
    for index in range(5):
        ingest(audit, path, str(index))
    complete(path, "4")
    worker = activity.evidence_worker
    worker.batch_size = 2
    assert worker.tick(now=100)["attempted"] == 2
    assert worker.tick(now=100)["attempted"] == 2
    assert worker.tick(now=100)["resolved"] == 1
    assert activity.repository.execution_results(["4"])["4"]["outcome"] == "success"


def test_file_budget_does_not_starve_the_oldest_completed_file(tmp_path, monkeypatch):
    audit, activity, path = setup(tmp_path, monkeypatch)
    ingest(audit, path, "oldest")
    complete(path, "oldest")
    for index in range(4):
        other = path.with_name(f"synthetic-{index}.jsonl")
        other.write_text(json.dumps({"type": "session_meta", "payload": {"id": "synthetic"}}) + "\n")
        ingest(audit, other, f"newer-{index}")
    first = activity.evidence_worker.tick(now=100)
    assert first["resolved"] == 1
    assert first["attempted"] == 4
    assert activity.evidence_worker.tick(now=100)["attempted"] == 1


def test_worker_lifecycle_stops_cleanly_and_isolates_tick_failures(tmp_path, monkeypatch):
    async def run():
        _, activity, _ = setup(tmp_path, monkeypatch)
        worker = activity.evidence_worker
        worker.interval = 0.01
        original = worker.tick
        count = 0

        def flaky():
            nonlocal count
            count += 1
            if count == 1:
                raise OSError("synthetic local failure")
            return original()

        monkeypatch.setattr(worker, "tick", flaky)
        await worker.start()
        for _ in range(100):
            if count >= 2:
                break
            await asyncio.sleep(0.01)
        await worker.stop()
        assert count >= 2
        assert worker.status()["state"] == "stopped"
    asyncio.run(run())


def test_app_lifespan_reconciles_without_workbench_queries(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from api import routes
    from main import create_app

    audit, activity, path = setup(tmp_path, monkeypatch)
    ref = ingest(audit, path)
    complete(path)
    monkeypatch.setattr(routes, "activity_service", activity)
    with TestClient(create_app()) as client:
        assert client.get("/health").json() == {"status": "ok"}
        for _ in range(100):
            if activity.repository.execution_results([ref]):
                break
            time.sleep(0.01)
        assert activity.repository.execution_results([ref])[ref]["outcome"] == "success"
    assert activity.evidence_worker.status()["state"] == "stopped"
