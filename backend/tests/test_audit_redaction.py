import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit.models import AuditEvent
from audit.redaction import redact_value


def test_redact_value_masks_sensitive_keys_and_bearer_tokens():
    value = {
        "api_key": "sk-live-secret",
        "headers": {"Authorization": "Bearer top-secret"},
        "command": "curl -H 'Authorization: Bearer hidden' https://example.test",
        "message": "keep this explanation",
    }

    redacted = redact_value(value)

    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["headers"]["Authorization"] == "[REDACTED]"
    assert "top-secret" not in redacted["command"]
    assert "hidden" not in redacted["command"]
    assert redacted["message"] == "keep this explanation"


def test_redact_value_masks_auth_formats_urls_and_secret_like_raw_values():
    value = {
        "basic": "Authorization: Basic dXNlcjpzZWNyZXQ=",
        "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature",
        "url": "https://example.test/callback?token=query-secret&next=ok",
        "cookie": "Cookie: session=private-session; theme=dark",
        "raw_secret": "sk-proj-1234567890abcdef",
        "normal": "Authorization is required for this operation",
    }

    redacted = redact_value(value)

    assert "dXNlcjpzZWNyZXQ=" not in redacted["basic"]
    assert "eyJhbGciOiJIUzI1NiJ9" not in redacted["jwt"]
    assert "query-secret" not in redacted["url"]
    assert "private-session" not in redacted["cookie"]
    assert redacted["raw_secret"] == "[REDACTED]"
    assert redacted["normal"] == value["normal"]


def test_audit_event_from_hook_keeps_contract_fields_without_raw_payload():
    event = AuditEvent.from_hook(
        {
            "event_id": "evt-1",
            "session_id": "session-1",
            "turn_id": "turn-2",
            "sequence": 3,
            "hook_event_name": "PostToolUse",
            "timestamp": "2026-08-06T10:00:00Z",
            "cwd": "D:/repo",
            "tool_name": "Bash",
            "tool_input": {"command": "git status", "token": "secret"},
            "tool_output": {"stdout": "clean"},
        }
    )

    assert event.event_id == "evt-1"
    assert event.event_type == "PostToolUse"
    assert event.session_id == "session-1"
    assert event.turn_id == "turn-2"
    assert event.sequence == 3
    assert event.details["tool_input"]["command"] == "git status"
    assert event.details["tool_input"]["token"] == "[REDACTED]"
    assert "raw_payload" not in event.to_dict()

    with pytest.raises((AttributeError, TypeError)):
        event.session_id = "other"


def test_audit_event_requires_session_and_event_type():
    with pytest.raises(ValueError, match="session_id"):
        AuditEvent.from_hook({"hook_event_name": "Stop"})

    with pytest.raises(ValueError, match="event type"):
        AuditEvent.from_hook({"session_id": "session-1"})
