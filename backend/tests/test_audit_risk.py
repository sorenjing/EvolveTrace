import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit.models import AuditEvent
from audit.risk import analyze_event
from audit.execution_results import execution_result


def event_with_command(command: str, **extra):
    payload = {
        "event_id": "evt-risk",
        "session_id": "session-risk",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    payload.update(extra)
    return AuditEvent.from_hook(payload)


def test_analyze_event_flags_dangerous_commands_with_stable_finding():
    findings = analyze_event(event_with_command("rm -rf ./dist"))

    assert len(findings) == 1
    assert findings[0].code == "dangerous_command"
    assert findings[0].severity == "high"
    assert findings[0].event_id == "evt-risk"


def test_analyze_event_records_a_pre_execution_safety_block():
    findings = analyze_event(
        event_with_command(
            "mkfs.ext4 /dev/sdb",
            safety={
                "decision": "deny",
                "rule_id": "disk_format",
                "reason": "Disk formatting is blocked.",
            },
        )
    )

    safety_findings = [finding for finding in findings if finding.code == "safety_block"]
    assert len(safety_findings) == 1
    assert safety_findings[0].severity == "high"
    assert safety_findings[0].evidence == "disk_format"


def test_analyze_event_flags_permission_denials_and_ignores_safe_commands():
    denied = event_with_command("git push", permission_denied=True)
    safe = event_with_command("git status")

    assert any(finding.code == "permission_denied" for finding in analyze_event(denied))
    assert analyze_event(safe) == []


def test_analyze_event_detects_post_tool_response_failure():
    failed = AuditEvent.from_hook(
        {
            "event_id": "evt-failed",
            "session_id": "session-risk",
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "tool_response": {"exit_code": 1, "stderr": "command failed"},
        }
    )

    assert any(finding.code == "tool_failure" for finding in analyze_event(failed))


@pytest.mark.parametrize("phase,details,outcome", [
    ("PostToolUse", {"exit_code": 0, "tool_response": "10 passed, 0 failed"}, "success"),
    ("PostToolUse", {"tool_response": "10 passed, 0 failed"}, "unknown"),
    ("PostToolUse", {"tool_response": {"exit_code": True}}, "unknown"),
    ("PostToolUse", {"tool_response": {"exit_code": "1"}}, "unknown"),
    ("PostToolUse", {"tool_response": {"exit_code": 0, "status": "failed"}}, "unknown"),
    ("PostToolUse", {"tool_response": {"exit_code": 2}}, "failure"),
    ("PostToolUse", {"exit_code": None, "tool_response": {"exit_code": 2}}, "failure"),
    ("PostToolUse", {"status": None, "tool_response": {"status": "failed"}}, "failure"),
    ("PostToolUse", {"exit_code": True, "status": False, "tool_response": {"exit_code": 2, "status": "failed"}}, "failure"),
    ("PostToolUse", {"exit_code": 0, "tool_response": {"exit_code": 2}}, "success"),
    ("PostToolUse", {"status": "cancelled", "tool_response": {"status": "failed"}}, "cancelled"),
    ("PreToolUse", {"exit_code": None, "tool_response": {"exit_code": 2}}, "pending"),
    ("PostToolUseFailure", {}, "failure"),
    ("PostToolUseFailure", {"status": "cancelled"}, "cancelled"),
])
def test_failure_finding_agrees_with_typed_outcome(phase, details, outcome):
    event = AuditEvent.from_hook({
        "event_id": "synthetic-outcome", "session_id": "synthetic-risk",
        "hook_event_name": phase, "tool_name": "Bash", **details,
    })
    assert execution_result(event.to_dict())["outcome"] == outcome
    assert any(item.code == "tool_failure" for item in analyze_event(event)) == (outcome == "failure")


@pytest.mark.parametrize("top_duration,expected", [(None, 12), (False, 12), (0, 0)])
def test_nested_duration_fallback_preserves_explicit_zero(top_duration, expected):
    event = AuditEvent.from_hook({"event_id": "synthetic-duration", "session_id": "synthetic-risk",
        "hook_event_name": "PostToolUse", "duration_ms": top_duration,
        "tool_response": {"exit_code": 2, "duration_ms": 12}})
    result = execution_result(event.to_dict())
    assert result["duration_ms"] == expected
    assert result["duration_source"] == "hook"


def test_apply_patch_event_derives_changed_files():
    event = AuditEvent.from_hook(
        {
            "event_id": "evt-patch",
            "session_id": "session-risk",
            "hook_event_name": "PostToolUse",
            "tool_name": "apply_patch",
            "tool_input": {
                "command": (
                    "*** Begin Patch\n"
                    "*** Update File: backend/audit/models.py\n"
                    "*** Add File: backend/tests/test_new.py\n"
                    "*** End Patch"
                )
            },
        }
    )

    assert event.details["changed_files"] == [
        "backend/audit/models.py",
        "backend/tests/test_new.py",
    ]
