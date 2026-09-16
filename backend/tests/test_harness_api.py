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
