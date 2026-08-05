import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from audit.repository import AuditRepository
from services.audit_service import AuditService
import api.routes as routes
from main import app


def test_audit_api_writes_reads_and_deletes_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "audit_service", AuditService(AuditRepository(tmp_path / "audit.db")))
    client = TestClient(app)
    payload = {
        "event_id": "evt-api-1",
        "session_id": "session-api",
        "turn_id": "turn-1",
        "sequence": 1,
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git status"},
    }

    response = client.post("/api/audit/events", json=payload)
    assert response.status_code == 201
    assert response.json()["event"]["event_id"] == "evt-api-1"

    sessions = client.get("/api/audit/sessions")
    assert sessions.status_code == 200
    assert sessions.json()[0]["session_id"] == "session-api"

    detail = client.get("/api/audit/sessions/session-api")
    assert detail.status_code == 200
    assert detail.json()["events"][0]["event_id"] == "evt-api-1"

    deleted = client.delete("/api/audit/sessions/session-api")
    assert deleted.status_code == 204
    assert client.get("/api/audit/sessions/session-api").status_code == 404


def test_audit_api_rejects_payload_without_required_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "audit_service", AuditService(AuditRepository(tmp_path / "audit.db")))
    response = TestClient(app).post("/api/audit/events", json={"tool_name": "Bash"})

    assert response.status_code == 422


def test_all_audit_routes_reject_non_loopback_clients():
    client = TestClient(app, client=("10.10.10.10", 12345))
    payload = {"session_id": "blocked", "hook_event_name": "Stop"}

    responses = [
        client.post("/api/audit/events", json=payload),
        client.get("/api/audit/sessions"),
        client.get("/api/audit/sessions/blocked"),
        client.delete("/api/audit/sessions/blocked"),
    ]

    assert [response.status_code for response in responses] == [403] * 4

    with pytest.raises(HTTPException, match="loopback"):
        routes.require_loopback(SimpleNamespace(client=SimpleNamespace(host="10.10.10.10")))

    stream_route = next(route for route in app.routes if route.path == "/api/audit/stream")
    assert any(dependency.call is routes.require_loopback for dependency in stream_route.dependencies)
