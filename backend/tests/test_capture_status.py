import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

import api.routes as routes
from audit.repository import AuditRepository
from services.activity_service import ActivityService
from services.audit_service import AuditService
from main import app


def services(tmp_path):
    audit = AuditService(AuditRepository(tmp_path / "audit.db"))
    return audit, ActivityService(audit.repository)


def test_capture_status_distinguishes_persisted_history_from_current_receipts(tmp_path):
    audit, activity = services(tmp_path)
    event = {"event_id": "one", "session_id": "s-1", "hook_event_name": "PostToolUse",
             "timestamp": "2001-01-01T00:00:00+00:00", "tool_name": "Bash", "tool_input": {"command": "git status"}}
    audit.ingest(event)
    audit.ingest(event)
    status = activity.status(audit.capture_status())
    assert status["schema_version"] == "activity-status/v1"
    assert status["capture_state"] == "receiving"
    assert status["received_event_count"] == 2
    assert status["persisted_event_count"] == 1
    assert status["stored_event_count"] == 1
    assert status["observed_phases"] == ["PostToolUse"]
    restarted = AuditService(audit.repository)
    idle = activity.status(restarted.capture_status())
    assert idle["capture_state"] == "awaiting_events"
    assert idle["stored_event_count"] == 1
    assert idle["received_event_count"] == 0
    assert idle["last_received_at"] is None
    assert "command" not in str(status)


def test_quiet_does_not_claim_hook_disconnection(tmp_path):
    audit, activity = services(tmp_path)
    audit.ingest({"event_id": "one", "session_id": "s-1", "hook_event_name": "PreToolUse"})
    capture = audit.capture_status()
    future = datetime.fromisoformat(capture["last_received_at"]) + timedelta(minutes=2)
    assert activity.status(capture, now=future)["capture_state"] == "quiet"


def test_status_includes_all_configured_hook_phases_without_arbitrary_names(tmp_path):
    audit, _ = services(tmp_path)
    phases = ["UserPromptSubmit", "SubagentStart", "SubagentStop", "PreCompact", "PostCompact"]
    for index, phase in enumerate(phases + ["private-unrecognized-phase"]):
        audit.ingest({"event_id": f"phase-{index}", "session_id": "s-1", "hook_event_name": phase})
    assert audit.capture_status()["observed_phases"] == sorted(phases)


def test_status_endpoint_reports_registration_and_rejects_remote_clients(tmp_path, monkeypatch):
    audit, activity = services(tmp_path)
    monkeypatch.setattr(routes, "audit_service", audit)
    monkeypatch.setattr(routes, "activity_service", activity)
    app.dependency_overrides[routes.require_loopback] = lambda: None
    try:
        response = TestClient(app).get("/api/activity/status")
        assert response.status_code == 200
        assert response.json()["registered_project_count"] == 0
        assert response.json()["capture_state"] == "awaiting_events"
    finally:
        app.dependency_overrides.pop(routes.require_loopback, None)
    assert TestClient(app, client=("10.1.1.1", 1000)).get("/api/activity/status").status_code == 403
