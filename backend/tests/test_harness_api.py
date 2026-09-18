import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import api.routes as routes
from harness.repository import HarnessRepository
from services.harness_service import HarnessService
from main import app


def bundle():
    return {"schema_version":"context-bundle/v1","project":"sample-app","generated_at":"2026-09-09T00:00:00+00:00","freshness":"current","observed_scope":["sample-app"],"repositories":[{"name":"sample-app","relative_path":"sample-app"}],"context":{"automatic":"facts","manual":"notes","global":"rules"}}


def client(tmp_path, monkeypatch):
    monkeypatch.setattr(routes, "harness_service", HarnessService(HarnessRepository(tmp_path / "harness.db")))
    app.dependency_overrides[routes.require_loopback] = lambda: None
    return TestClient(app)


def test_context_import_rejects_unknown_schema(tmp_path, monkeypatch):
    response = client(tmp_path, monkeypatch).post("/api/harness/context-snapshots", json={"schema_version": "context-bundle/v2"})
    assert response.status_code == 422


def test_context_import_rejects_absolute_paths(tmp_path, monkeypatch):
    value = bundle(); value["repositories"][0]["relative_path"] = r"C:\private\repo"
    assert client(tmp_path, monkeypatch).post("/api/harness/context-snapshots", json=value).status_code == 422


def test_context_import_rejects_absolute_paths_outside_repository_entries(tmp_path, monkeypatch):
    value = bundle(); value["observed_scope"] = ["/Users/example/sample-app"]
    assert client(tmp_path, monkeypatch).post("/api/harness/context-snapshots", json=value).status_code == 422


def test_context_import_rejects_embedded_absolute_paths(tmp_path, monkeypatch):
    value = bundle(); value["context"]["automatic"] = "workspace at C:/Users/example/sample-app"
    assert client(tmp_path, monkeypatch).post("/api/harness/context-snapshots", json=value).status_code == 422


def test_context_import_rejects_absolute_paths_after_assignments(tmp_path, monkeypatch):
    value = bundle(); value["context"]["automatic"] = "root=C:/Users/example/sample-app"
    assert client(tmp_path, monkeypatch).post("/api/harness/context-snapshots", json=value).status_code == 422


def test_context_import_rejects_unc_paths(tmp_path, monkeypatch):
    value = bundle(); value["context"]["automatic"] = r"root=\\server\share\sample-app"
    assert client(tmp_path, monkeypatch).post("/api/harness/context-snapshots", json=value).status_code == 422


def test_context_import_and_task_crud(tmp_path, monkeypatch):
    api = client(tmp_path, monkeypatch)
    snapshot = api.post("/api/harness/context-snapshots", json=bundle())
    assert snapshot.status_code == 201
    task = api.post("/api/harness/tasks", json={"title":"Ship harness","goal":"Import a versioned context bundle","target_repositories":["sample-app"],"constraints":[],"acceptance_criteria":["Tests pass"],"open_questions":[],"risk_level":"normal","status":"ready","context_snapshot_id":snapshot.json()["snapshot_id"]})
    assert task.status_code == 201
    assert api.get("/api/harness/tasks").json()[0]["task_id"] == task.json()["task_id"]
    detail = api.get(f"/api/harness/tasks/{task.json()['task_id']}")
    assert detail.status_code == 200
    assert detail.json()["context_snapshot"]["freshness"] == "current"
    assert detail.json()["runs"] == []


def test_external_task_id_and_receipt_round_trip_are_idempotent(tmp_path, monkeypatch):
    api = client(tmp_path, monkeypatch)
    snapshot = api.post("/api/harness/context-snapshots", json=bundle()).json()
    task_payload = {
        "task_id": "task-external-1",
        "title": "Ship harness",
        "goal": "Bind observable context",
        "target_repositories": ["sample-app"],
        "constraints": [],
        "acceptance_criteria": [],
        "open_questions": [],
        "risk_level": "normal",
        "status": "ready",
        "context_snapshot_id": snapshot["snapshot_id"],
    }
    first_task = api.post("/api/harness/tasks", json=task_payload)
    replayed_task = api.post("/api/harness/tasks", json=task_payload)
    assert first_task.status_code == 201
    assert replayed_task.json()["task_id"] == "task-external-1"

    receipt = {
        "schema": "context-receipt/v1",
        "receipt_id": "receipt-1",
        "task_id": "task-external-1",
        "context_snapshot_id": snapshot["snapshot_id"],
        "attempt_id": "unassigned",
        "bundle_id": "ctx_1",
        "platform": "codex",
        "adapter": "evolvetrace-http",
        "status": "delivered",
        "delivered_source_ids": ["context:sample-app:rendered"],
        "loaded_skill_ids": [],
    }
    assert api.post("/api/harness/context-receipts", json=receipt).status_code == 201
    receipts = api.get("/api/harness/tasks/task-external-1/context-receipts")
    assert receipts.status_code == 200
    assert receipts.json()[0]["receipt_id"] == "receipt-1"


def test_execution_profile_api_round_trip(tmp_path, monkeypatch):
    api = client(tmp_path, monkeypatch)
    payload = {
        "schema": "execution-profile/v1",
        "profile_id": "codex-local",
        "platform": "codex",
        "harness": "codex-work",
        "adapter": "openai-plugin",
        "adapter_version": "1.0.0",
        "provider": "openai",
        "model": None,
        "capabilities": ["mcp", "skills"],
        "policy_profile": "local-reviewed",
    }
    assert api.post("/api/harness/execution-profiles", json=payload).status_code == 201
    response = api.get("/api/harness/execution-profiles/codex-local")
    assert response.status_code == 200
    assert response.json()["model"] is None
