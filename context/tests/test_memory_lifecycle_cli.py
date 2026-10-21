from evolvetrace_context import audit_client
from evolvetrace_context.cli import main
from test_cli import make_workspace


def test_cli_forwards_applicability_expiry_and_replacement(tmp_path, monkeypatch):
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    calls = []
    monkeypatch.setattr(audit_client, "request_json", lambda origin, method, path, payload=None: calls.append((method, path, payload)) or {})
    assert main(["audit", "remember", "demo", "--workspace", str(tmp_path), "--session-id", "s",
                 "--event-id", "e", "--note", "Synthetic observation", "--confirm", "--applies-to", "Synthetic test tasks",
                 "--expires-at", "2035-01-01T00:00:00+00:00", "--supersedes", "older-memory"]) == 0
    payload = calls[-1][2]
    assert payload["applicability"] == "Synthetic test tasks"
    assert payload["supersedes"] == "older-memory"
    assert payload["expires_at"] == "2035-01-01T00:00:00+00:00"


def test_cli_revoke_requires_confirmation(tmp_path, monkeypatch):
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    calls = []
    monkeypatch.setattr(audit_client, "request_json", lambda origin, method, path, payload=None: calls.append((method, path, payload)) or {})
    args = ["audit", "revoke", "demo", "--workspace", str(tmp_path), "--memory-id", "memory-1"]
    assert main(args) != 0
    assert calls == []
    assert main([*args, "--confirm"]) == 0
    assert calls[-1][0:2] == ("POST", "/activity/memory/memory-1/revoke")


def test_memory_applicability_is_delivered_with_observation(tmp_path, monkeypatch):
    monkeypatch.setattr(audit_client, "read_memory", lambda *args: {
        "project": {"project_id": "demo-id"}, "entries": [{"memory_id": "m-1", "note": "Synthetic note",
        "evidence_refs": ["e-1"], "applicability": "Only synthetic unit tests", "expires_at": "2035-01-01T00:00:00+00:00"}]})
    result = {"context": "Only the listed local sources were read.", "receipt": {"project": "demo"}}
    audit_client.append_memory(tmp_path, result, "demo", "http://127.0.0.1:8001")
    assert "Only synthetic unit tests" in result["context"]
    assert "2035-01-01" in result["context"]
