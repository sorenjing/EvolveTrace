import pytest
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from evolvetrace_context import audit_client
from evolvetrace_context.cli import main
from evolvetrace_context.config import ConfigError
from test_cli import make_workspace


def workspace(tmp_path, capsys):
    make_workspace(tmp_path)
    assert main(["init", "--workspace", str(tmp_path)]) == 0
    memory = tmp_path / ".ai/projects/demo.md"
    memory.write_text(memory.read_text(encoding="utf-8").replace(
        "Record goals, architecture decisions, constraints, current state, and known issues here.",
        "Keep project checks local and use scoped searches."), encoding="utf-8")
    capsys.readouterr()


def test_sync_dry_run_uses_discovery_without_memory_or_network_changes(tmp_path, capsys, monkeypatch):
    workspace(tmp_path, capsys)
    before = (tmp_path / ".ai/projects/demo.md").read_bytes()
    monkeypatch.setattr(audit_client, "request_json", lambda *args: pytest.fail("dry run must be offline"))
    assert main(["audit", "sync", "--workspace", str(tmp_path), "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert '"schema_version": "workspace-index/v1"' in output
    assert '"relative_path": "projects/demo"' in output
    assert (tmp_path / ".ai/projects/demo.md").read_bytes() == before


def test_hook_can_opt_in_to_only_its_selected_project_memory(tmp_path, capsys, monkeypatch):
    from evolvetrace_context.context_delivery import session_start
    workspace(tmp_path, capsys)
    identity = audit_client.selected_project(tmp_path, "demo")
    monkeypatch.setenv("EVOLVETRACE_AUDIT_MEMORY_URL", "http://127.0.0.1:8001")
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(tmp_path / "projects/demo"), "source": "startup"})))
    monkeypatch.setattr(audit_client, "request_json", lambda *args: {"schema_version": "audit-memory/v1", "project": {"project_id": identity},
        "entries": [{"memory_id": "m-1", "status": "human_reviewed", "note": "Narrow scans", "evidence_refs": ["e-1"]}]})
    assert session_start() == 0
    assert "Narrow scans" in capsys.readouterr().out


def test_real_loopback_transport_and_redirect_rejection():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.endswith("redirect"):
                self.send_response(302)
                self.send_header("Location", "https://external.example/")
                self.end_headers()
                return
            body = b'{"schema_version":"workspace-activity/v1"}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *args):
            return
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever)
    thread.start()
    try:
        origin = f"http://127.0.0.1:{server.server_port}"
        assert audit_client.request_json(origin, "GET", "/activity/report")["schema_version"] == "workspace-activity/v1"
        with pytest.raises(ConfigError):
            audit_client.request_json(origin, "GET", "/redirect")
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_project_report_and_memory_are_scoped_by_workspace(tmp_path, capsys, monkeypatch):
    workspace(tmp_path, capsys)
    identity = audit_client.selected_project(tmp_path, "demo")
    calls = []
    def request(origin, method, path, payload=None):
        calls.append(path)
        return {"schema_version": "audit-memory/v1", "project": {"project_id": identity},
                "entries": [{"memory_id": "m-1", "status": "human_reviewed", "note": "Narrow scans", "evidence_refs": ["e-1"]}]}
    monkeypatch.setattr(audit_client, "request_json", request)
    assert main(["audit", "memory", "demo", "--workspace", str(tmp_path)]) == 0
    assert calls == [f"/activity/memory/{identity}"]
    assert "Narrow scans" in capsys.readouterr().out
    with pytest.raises(ConfigError, match="unknown project"):
        audit_client.selected_project(tmp_path, "other")


def test_optional_load_returns_only_reviewed_memory_and_no_semantic_writes(tmp_path, capsys, monkeypatch):
    workspace(tmp_path, capsys)
    identity = audit_client.selected_project(tmp_path, "demo")
    before = (tmp_path / ".ai/projects/demo.md").read_bytes()
    monkeypatch.setattr(audit_client, "request_json", lambda *args: {"schema_version": "audit-memory/v1", "project": {"project_id": identity},
        "entries": [{"memory_id": "m-1", "status": "human_reviewed", "note": "Use scoped scans", "evidence_refs": ["e-1"]},
                    {"memory_id": "m-2", "status": "candidate", "note": "Unreviewed inference", "evidence_refs": []}]})
    assert main(["load", "demo", "--workspace", str(tmp_path), "--audit-url", "http://127.0.0.1:8001", "--json"]) == 0
    output = capsys.readouterr().out
    assert "Use scoped scans" in output
    assert "Unreviewed inference" not in output
    assert "historical" in output
    assert (tmp_path / ".ai/projects/demo.md").read_bytes() == before
    assert main(["usage", "demo", "--workspace", str(tmp_path), "--json"]) == 0
    assert '"memory_ids": ["m-1"]' in capsys.readouterr().out


def test_optional_load_is_fail_open_but_explicit_audit_reports_failure(tmp_path, capsys, monkeypatch):
    workspace(tmp_path, capsys)
    def unavailable(*args):
        raise ConfigError("local audit service unavailable")
    monkeypatch.setattr(audit_client, "request_json", unavailable)
    assert main(["load", "demo", "--workspace", str(tmp_path), "--audit-url", "http://127.0.0.1:8001"]) == 0
    assert "audit_memory_unavailable" in capsys.readouterr().out
    assert main(["audit", "report", "--workspace", str(tmp_path)]) == 2


def test_client_rejects_external_origins_and_cross_project_response(tmp_path, capsys, monkeypatch):
    for origin in ("https://external.example", "http://user:pass@127.0.0.1", "http://127.0.0.1?token=x"):
        with pytest.raises(ConfigError):
            audit_client.request_json(origin, "GET", "/activity/report")
    workspace(tmp_path, capsys)
    monkeypatch.setattr(audit_client, "request_json", lambda *args: {"schema_version": "audit-memory/v1", "project": {"project_id": "another-project"}, "entries": []})
    with pytest.raises(ConfigError, match="mismatched project"):
        audit_client.read_memory(tmp_path, "demo", "http://127.0.0.1:8001")


def test_remember_requires_explicit_confirmation_and_sends_evidence(tmp_path, capsys, monkeypatch):
    workspace(tmp_path, capsys)
    calls = []
    monkeypatch.setattr(audit_client, "request_json", lambda *args: calls.append(args) or {"status": "human_reviewed"})
    args = ["audit", "remember", "demo", "--workspace", str(tmp_path), "--session-id", "s-1", "--event-id", "e-1", "--note", "Narrow scans"]
    assert main(args) == 2
    assert calls == []
    assert main(args + ["--confirm"]) == 0
    assert calls[0][3]["evidence_refs"] == ["e-1"]
    assert calls[0][3]["confirmed"] is True
