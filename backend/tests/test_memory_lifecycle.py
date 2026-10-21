from datetime import datetime, timedelta, timezone

import pytest

from test_workspace_activity import setup, register


def saved(client, audit, root, project_id, **extra):
    audit.ingest({"event_id": "memory-source", "session_id": "memory-session", "hook_event_name": "PostToolUse",
                  "cwd": str(root / "projects/demo"), "tool_name": "Bash", "tool_input": {"command": "npm test"}})
    return client.post("/api/activity/memory", json={"project_id": project_id, "session_id": "memory-session",
        "note": "Synthetic scoped guidance", "evidence_refs": ["memory-source"], "confirmed": True, **extra})


def test_revoked_memory_is_excluded_from_recall_but_preserved_in_history(setup):
    client, audit, activity, root = setup
    index, _ = register(client, root)
    project = index["projects"][0]["project_id"]
    entry = saved(client, audit, root, project).json()
    url = "/api/activity/memory/" + entry["memory_id"] + "/revoke"
    assert client.post(url, json={"project_id": project, "confirmed": False}).status_code == 422
    assert client.post(url, json={"project_id": project, "confirmed": True}).status_code == 200
    assert client.post(url, json={"project_id": project, "confirmed": True}).status_code == 200
    result = activity.memory(project)
    assert result["entries"] == []
    assert result["history"][0]["status"] == "revoked"
    assert result["history"][0]["note"] == entry["note"]


def test_memory_replacement_is_project_scoped_and_atomic(setup):
    client, audit, activity, root = setup
    index, _ = register(client, root)
    project = index["projects"][0]["project_id"]
    original = saved(client, audit, root, project).json()
    replacement = saved(client, audit, root, project, supersedes=original["memory_id"], applicability="Only synthetic CLI tests")
    assert replacement.status_code == 201
    assert [entry["memory_id"] for entry in activity.memory(project)["entries"]] == [replacement.json()["memory_id"]]
    assert any(row["status"] == "superseded" for row in activity.memory(project)["history"])
    other = index["projects"][1]["project_id"]
    assert client.post("/api/activity/memory/" + replacement.json()["memory_id"] + "/revoke",
                       json={"project_id": other, "confirmed": True}).status_code == 422
    before = activity.memory(project)
    assert saved(client, audit, root, project, supersedes="missing").status_code == 422
    assert activity.memory(project) == before


def test_expired_guidance_not_returned_and_bad_expiry_rejected(setup):
    client, audit, activity, root = setup
    index, _ = register(client, root)
    project = index["projects"][0]["project_id"]
    future = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    entry = saved(client, audit, root, project, expires_at=future).json()
    with activity.repository._connect() as connection:
        connection.execute("UPDATE activity_memory SET expires_at=? WHERE memory_id=?", ("2000-01-01T00:00:00+00:00", entry["memory_id"]))
    assert activity.memory(project)["entries"] == []
    assert activity.memory(project)["history"][0]["status"] == "expired"
    assert saved(client, audit, root, project, expires_at="tomorrow").status_code == 422
    assert saved(client, audit, root, project, expires_at="2000-01-01T00:00:00").status_code == 422


def test_pre_lifecycle_database_preserves_confirmed_memory(setup):
    from services.activity_service import ActivityService
    client, audit, activity, root = setup
    index, _ = register(client, root)
    project = index["projects"][0]["project_id"]
    original = saved(client, audit, root, project).json()
    with activity.repository._connect() as connection:
        for column in ("memory_status", "applicability", "expires_at", "supersedes"):
            connection.execute(f"ALTER TABLE activity_memory DROP COLUMN {column}")
    migrated = ActivityService(audit.repository).memory(project)
    assert migrated["history"] == []
    assert migrated["entries"][0]["memory_id"] == original["memory_id"]
    assert migrated["entries"][0]["note"] == original["note"]
    assert migrated["entries"][0]["status"] == "human_reviewed"
