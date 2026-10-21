import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient

import api.routes as routes
from main import app
from audit.repository import AuditRepository
from services.audit_service import AuditService
from services.activity_service import ActivityService
from test_activity import event


@pytest.fixture
def setup(tmp_path, monkeypatch):
    audit = AuditService(AuditRepository(tmp_path / "audit.db"))
    activity = ActivityService(audit.repository)
    monkeypatch.setattr(routes, "audit_service", audit)
    monkeypatch.setattr(routes, "activity_service", activity)
    app.dependency_overrides[routes.require_loopback] = lambda: None
    yield TestClient(app), audit, activity, tmp_path
    app.dependency_overrides.pop(routes.require_loopback, None)


def register(client, root):
    payload = {"schema_version": "workspace-index/v1", "workspace_root": str(root),
               "projects": [{"name": "demo", "relative_path": "projects/demo"},
                            {"name": "nested", "relative_path": "projects/demo/nested"}]}
    response = client.post("/api/activity/workspaces", json=payload)
    assert response.status_code == 201
    return response.json(), payload


def ingest(audit, root, session="s-1", nested=False):
    for index in range(5):
        payload = event(index)
        payload["hook_event_name"] = payload.pop("event_type")
        payload.update(payload.pop("details"))
        payload["session_id"] = session
        payload["event_id"] = f"{session}-{index}"
        payload["cwd"] = str(root / "projects/demo" / ("nested/sub" if nested else "src"))
        audit.ingest(payload)


def recall_fixture(setup):
    client, audit, activity, root = setup
    index, _ = register(client, root)
    ingest(audit, root)
    project_id = index["projects"][0]["project_id"]
    memory = activity.remember({"project_id": project_id, "session_id": "s-1", "note": "Use the scoped check",
                                "evidence_refs": ["s-1-0"], "confirmed": True})
    payload = {"schema_version": "audit-memory-recall/v1", "project_id": project_id,
               "reported_at": "2026-01-01T00:00:00+00:00", "trigger": "manual", "context_status": "returned",
               "context_freshness": "current", "memory_ids": [memory["memory_id"]], "truncated": False}
    return client, activity, index, payload


def test_memory_reads_do_not_count_as_returns_and_reports_are_deduplicated(setup):
    client, activity, index, payload = recall_fixture(setup)
    url = "/api/activity/memory/" + payload["project_id"]
    assert client.get(url).json()["recalls"] == []
    first = client.post("/api/activity/memory-recalls", json=payload)
    assert first.status_code == 201
    assert client.post("/api/activity/memory-recalls", json=payload).json() == first.json()
    saved = client.get(url).json()["recalls"]
    assert len(saved) == 1
    assert saved[0]["memory_ids"] == payload["memory_ids"]
    assert saved[0]["authority"] == "client_reported_output"
    assert saved[0]["model_use"] == "unknown"
    assert client.get(url).json()["recalls"] == saved
    restarted = ActivityService(activity.audit_repository)
    assert restarted.memory(payload["project_id"])["recalls"] == saved
    other = index["projects"][1]["project_id"]
    assert client.get("/api/activity/memory/" + other).json()["recalls"] == []


@pytest.mark.parametrize("changes", [
    {"schema_version": "unknown"}, {"prompt": "synthetic text must not be stored"},
    {"reported_at": "not-a-time"}, {"reported_at": "2026-01-01T00:00:00"},
    {"memory_ids": ["missing"]}, {"memory_ids": ["missing"] * 21},
    {"trigger": "model-used"}, {"truncated": "false"}, {"context_status": "accepted"},
    {"model_use": "understood"},
])
def test_recall_report_rejects_unbounded_private_or_invalid_claims(setup, changes):
    client, _, _, payload = recall_fixture(setup)
    assert client.post("/api/activity/memory-recalls", json={**payload, **changes}).status_code == 422
    assert client.get("/api/activity/memory/" + payload["project_id"]).json()["recalls"] == []


def test_recall_history_checks_project_ownership_and_bounds_persisted_records(setup):
    client, activity, index, payload = recall_fixture(setup)
    other = index["projects"][1]["project_id"]
    assert client.post("/api/activity/memory-recalls", json={**payload, "project_id": other}).status_code == 422
    empty = {**payload, "project_id": other, "memory_ids": []}
    assert client.post("/api/activity/memory-recalls", json=empty).status_code == 201
    for second in range(23):
        report = {**payload, "reported_at": f"2026-01-01T00:00:{second:02d}+00:00"}
        assert client.post("/api/activity/memory-recalls", json=report).status_code == 201
    history = activity.memory(payload["project_id"])["recalls"]
    assert len(history) == 20
    assert history[0]["reported_at"] == "2026-01-01T00:00:22+00:00"
    with activity.repository._connect() as connection:
        count = connection.execute("SELECT COUNT(*) FROM activity_memory_recalls WHERE project_id=?", (payload["project_id"],)).fetchone()[0]
    assert count == 20


def test_registration_is_idempotent_nested_and_backfills_prior_events(setup):
    client, audit, _, root = setup
    ingest(audit, root)
    ingest(audit, root, "s-2", nested=True)
    result, payload = register(client, root)
    assert client.post("/api/activity/workspaces", json=payload).json() == result
    report = client.get("/api/activity/report").json()
    projects = {p["name"]: p for p in report["projects"]}
    assert projects["demo"]["activity"]["attempt_count"] == 5
    assert projects["nested"]["activity"]["attempt_count"] == 5
    assert report["unattributed_event_count"] == 0
    assert str(root) not in str(report)
    assert "workspace_root" not in str(result)


def test_ignore_mute_reviewed_memory_and_restart(setup):
    client, audit, activity, root = setup
    result, _ = register(client, root)
    project = result["projects"][0]
    ingest(audit, root)
    url = "/api/activity/report?project_id=" + project["project_id"]
    finding = client.get(url).json()["projects"][0]["activity"]["findings"][0]
    decision = {"project_id": project["project_id"], "session_id": "s-1", "finding_id": finding["finding_id"], "code": finding["code"], "action": "ignore"}
    assert client.post("/api/activity/decisions", json=decision).status_code == 201
    assert client.get(url).json()["projects"][0]["activity"]["findings"][0]["suppressed"] is True
    decision["action"] = "mute"
    assert client.post("/api/activity/decisions", json=decision).status_code == 201
    memory = {"project_id": project["project_id"], "session_id": "s-1", "note": "Prefer a scoped search", "evidence_refs": finding["evidence_refs"], "confirmed": True}
    response = client.post("/api/activity/memory", json=memory)
    assert response.status_code == 201
    restarted = ActivityService(audit.repository)
    saved = restarted.memory(project["project_id"])
    assert saved["entries"][0]["note"] == memory["note"]
    assert saved["entries"][0]["status"] == "human_reviewed"
    assert saved == activity.memory(project["project_id"])
    assert client.delete("/api/audit/sessions/s-1").status_code == 204
    assert restarted.memory(project["project_id"])["entries"] == []


def test_memory_requires_confirmation_matching_project_and_evidence(setup):
    client, audit, _, root = setup
    result, _ = register(client, root)
    ingest(audit, root)
    base = {"project_id": result["projects"][0]["project_id"], "session_id": "s-1", "note": "Scoped search", "evidence_refs": ["s-1-0"], "confirmed": True}
    for changes in ({"confirmed": False}, {"evidence_refs": ["missing"]}, {"project_id": result["projects"][1]["project_id"]}, {"note": ""}, {"confirmed": "true"}):
        assert client.post("/api/activity/memory", json={**base, **changes}).status_code == 422
    response = client.post("/api/activity/memory", json={**base, "note": "password=synthetic-only"})
    assert response.status_code == 201
    assert "synthetic-only" not in response.text


def test_index_validation_unknown_paths_bounded_queries_and_isolation(setup):
    client, audit, _, root = setup
    result, payload = register(client, root)
    for relative in ("../outside", "/outside", "C:/outside", "projects/../../outside"):
        assert client.post("/api/activity/workspaces", json={**payload, "projects": [{"name": "demo", "relative_path": relative}]}).status_code == 422
    ingest(audit, root / "unregistered")
    report = client.get("/api/activity/report?limit=2").json()
    assert report["truncated"] is True
    assert report["observed_event_count"] == 2
    assert report["unattributed_event_count"] == 2
    assert client.get("/api/activity/report?limit=0").status_code == 422
    assert client.get("/api/activity/report?project_id=unknown").status_code == 404
    other, _ = register(client, root / "second-workspace")
    assert result["projects"][0]["project_id"] != other["projects"][0]["project_id"]


def test_new_routes_require_loopback():
    client = TestClient(app, client=("10.1.1.1", 1000))
    assert client.get("/api/activity/report").status_code == 403
    assert client.get("/api/activity/memory/unknown").status_code == 403
    assert client.post("/api/activity/memory/unknown/revoke", json={"confirmed": True}).status_code == 403
    for path in ("workspaces", "decisions", "memory"):
        assert client.post("/api/activity/" + path, json={}).status_code == 403


def test_project_matching_is_bounded_by_distinct_directories(setup, monkeypatch):
    client, audit, activity, root = setup
    register(client, root)
    ingest(audit, root)
    count = 0
    original = activity._match
    def measured(*args):
        nonlocal count
        count += 1
        return original(*args)
    monkeypatch.setattr(activity, "_match", measured)
    assert client.get("/api/activity/report").status_code == 200
    assert count == 1


def test_invalid_captured_directory_stays_unattributed(setup):
    client, audit, _, root = setup
    register(client, root)
    payload = event(1)
    payload["hook_event_name"] = payload.pop("event_type")
    payload.update(payload.pop("details"))
    payload["cwd"] = "bad\x00path"
    audit.ingest(payload)
    assert client.get("/api/activity/report").json()["unattributed_event_count"] == 1


def test_invalid_decision_types_return_validation_error(setup):
    client, _, _, root = setup
    result, _ = register(client, root)
    payload = {"project_id": result["projects"][0]["project_id"], "action": {}, "code": []}
    assert client.post("/api/activity/decisions", json=payload).status_code == 422


def test_overall_statistics_include_unattributed_workspace_commands(setup):
    client, audit, _, root = setup
    register(client, root)
    ingest(audit, root / "unregistered")
    report = client.get("/api/activity/report").json()
    assert report["overall_activity"]["attempt_count"] == 5
    assert report["overall_activity"]["categories"]["read_search"] == 5
    assert report["unattributed_event_count"] == 5
    assert all(project["activity"]["attempt_count"] == 0 for project in report["projects"])
