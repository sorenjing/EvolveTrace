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


@pytest.mark.parametrize("explicit_url,expected_note", [
    (None, "Environment-selected reviewed observation"),
    ("http://127.0.0.1:8022", "Explicitly-selected reviewed observation"),
])
def test_project_switch_load_keeps_recall_opt_in_and_explicit_override(
    tmp_path, capsys, monkeypatch, explicit_url, expected_note
):
    workspace(tmp_path, capsys)
    identity = audit_client.selected_project(tmp_path, "demo")
    before = (tmp_path / ".ai/projects/demo.md").read_bytes()
    monkeypatch.setenv("EVOLVETRACE_AUDIT_MEMORY_URL", "http://127.0.0.1:8021")

    def response(origin, method, path, payload=None):
        if method == "POST":
            return {"schema_version": "audit-memory-recall/v1", "recall_id": "r-switch"}
        notes = {"http://127.0.0.1:8021": "Environment-selected reviewed observation",
                 "http://127.0.0.1:8022": "Explicitly-selected reviewed observation"}
        assert method == "GET" and path == f"/activity/memory/{identity}"
        return {"schema_version": "audit-memory/v1", "project": {"project_id": identity},
                "entries": [{"memory_id": "m-switch", "project_id": identity,
                             "session_id": "s-demo", "status": "human_reviewed",
                             "created_at": "2026-01-01T00:00:00+00:00",
                             "note": notes[origin], "evidence_refs": ["e-demo"]}],
                "limit": 20, "authority": "human_reviewed_observation", "freshness": "historical"}

    monkeypatch.setattr(audit_client, "request_json", response)
    args = ["load", "demo", "--workspace", str(tmp_path), "--json"]
    if explicit_url:
        args += ["--audit-url", explicit_url]
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert expected_note in result["context"]
    assert result["receipt"]["audit_memory"]["memory_ids"] == ["m-switch"]
    assert (tmp_path / ".ai/projects/demo.md").read_bytes() == before


def test_project_switch_without_recall_opt_in_stays_offline(tmp_path, capsys, monkeypatch):
    workspace(tmp_path, capsys)
    monkeypatch.delenv("EVOLVETRACE_AUDIT_MEMORY_URL", raising=False)
    monkeypatch.setattr(audit_client, "request_json", lambda *args: pytest.fail("offline load contacted audit service"))
    assert main(["load", "demo", "--workspace", str(tmp_path), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert "audit_memory" not in result["receipt"]


@pytest.mark.parametrize("mode", ["load", "hook"])
@pytest.mark.parametrize("report_fails", [False, True])
def test_recall_report_follows_output_and_failure_never_blocks_context(
    tmp_path, capsys, monkeypatch, mode, report_fails
):
    from contextlib import redirect_stdout
    from evolvetrace_context.context_delivery import session_start
    workspace(tmp_path, capsys)
    identity = audit_client.selected_project(tmp_path, "demo")
    monkeypatch.setenv("EVOLVETRACE_AUDIT_MEMORY_URL", "http://127.0.0.1:8001")
    output = io.StringIO()
    reports = []

    def transport(origin, method, path, payload=None):
        if method == "GET":
            return {"schema_version": "audit-memory/v1", "project": {"project_id": identity},
                    "entries": [{"memory_id": "m-returned", "status": "human_reviewed",
                                 "note": "Synthetic reviewed lesson", "evidence_refs": ["e-1"]}]}
        assert "Synthetic reviewed lesson" in output.getvalue()
        assert path == "/activity/memory-recalls"
        reports.append(payload)
        if report_fails:
            raise ConfigError("synthetic service failure")
        return {"schema_version": "audit-memory-recall/v1", "recall_id": "r-demo"}

    monkeypatch.setattr(audit_client, "request_json", transport)
    with redirect_stdout(output):
        if mode == "hook":
            monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(tmp_path / "projects/demo"), "source": "startup"})))
            code = session_start()
        else:
            code = main(["load", "demo", "--workspace", str(tmp_path), "--json"])
    assert code == 0
    assert "Synthetic reviewed lesson" in output.getvalue()
    assert len(reports) == 1
    assert set(reports[0]) == {"schema_version", "project_id", "reported_at", "trigger", "context_status", "context_freshness", "memory_ids", "truncated"}
    assert reports[0]["memory_ids"] == ["m-returned"]
    assert reports[0]["project_id"] == identity
    assert reports[0]["trigger"] == ("manual" if mode == "load" else "SessionStart:startup")
    assert reports[0]["schema_version"] == "audit-memory-recall/v1"
    assert "Synthetic reviewed lesson" not in json.dumps(reports[0])
    assert ("audit_recall_not_reported" in capsys.readouterr().err) is report_fails


def test_failed_stdout_never_reports_a_returned_memory(tmp_path, capsys, monkeypatch):
    from evolvetrace_context.context_delivery import emit_context, prepare_context
    workspace(tmp_path, capsys)
    root, result = prepare_context(tmp_path, "demo")
    result["receipt"]["audit_memory"] = {"status": "returned", "project_id": "demo", "memory_ids": ["m-1"], "truncated": False}

    class BrokenOutput:
        def write(self, value):
            raise BrokenPipeError("synthetic broken pipe")

    monkeypatch.setattr(audit_client, "request_json", lambda *args: pytest.fail("broken output was reported as returned"))
    monkeypatch.setattr("sys.stdout", BrokenOutput())
    with pytest.raises(BrokenPipeError):
        emit_context(root, result, audit_url="http://127.0.0.1:8001")


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
