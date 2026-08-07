import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "plugin" / "hooks" / "capture_event.py"


def load_capture_module():
    spec = importlib.util.spec_from_file_location("capture_event", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hook_capture_posts_redacted_contract_payload(monkeypatch):
    capture_event = load_capture_module()
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return object()

    monkeypatch.setattr(capture_event.urllib.request, "urlopen", fake_urlopen)
    payload = {
        "session_id": "session-hook",
        "hook_event_name": "PreToolUse",
        "api_key": "secret",
        "tool_input": {"command": "git status"},
    }

    assert capture_event.capture(payload) is True
    body = json.loads(captured["request"].data.decode("utf-8"))
    assert body["session_id"] == "session-hook"
    assert body["api_key"] == "[REDACTED]"
    assert captured["request"].headers["Content-type"] == "application/json"
    assert captured["timeout"] <= 2


def test_hook_capture_redacts_auth_and_jwt_values():
    capture_event = load_capture_module()
    value = {
        "authorization": "Basic dXNlcjpzZWNyZXQ=",
        "token_url": "https://example.test?token=query-secret",
        "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature",
    }

    redacted = capture_event.redact_value(value)

    assert "dXNlcjpzZWNyZXQ=" not in redacted["authorization"]
    assert "query-secret" not in redacted["token_url"]
    assert "eyJhbGciOiJIUzI1NiJ9" not in redacted["jwt"]


def test_hook_capture_returns_zero_when_backend_is_unavailable():
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=json.dumps({"session_id": "session-hook", "hook_event_name": "Stop"}),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0


def test_plugin_manifest_and_hooks_configuration_exist():
    manifest = json.loads((ROOT / "plugin" / ".codex-plugin" / "plugin.json").read_text())
    hooks = json.loads((ROOT / "plugin" / "hooks" / "hooks.json").read_text())

    assert manifest["name"] == "evolvetrace"
    assert "hooks" in manifest
    assert "hooks" in hooks


def test_plugin_hooks_use_matcher_groups_and_current_compaction_events():
    hooks = json.loads((ROOT / "plugin" / "hooks" / "hooks.json").read_text())
    configured_events = hooks["hooks"]

    assert "ContextCompacted" not in configured_events
    assert {"PreCompact", "PostCompact"} <= configured_events.keys()
    for groups in configured_events.values():
        assert groups
        for group in groups:
            assert isinstance(group, dict)
            assert group["matcher"] == ".*"
            assert isinstance(group["hooks"], list)
            assert "$" + "{PLUGIN_ROOT}" in group["hooks"][0]["command"]
