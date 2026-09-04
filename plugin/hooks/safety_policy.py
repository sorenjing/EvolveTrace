from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class SafetyDecision:
    decision: str
    rule_id: str = ""
    reason: str = ""

    @property
    def denied(self) -> bool:
        return self.decision == "deny"


_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "disk_format",
        "EvolveTrace blocked a command that may format or erase a storage device.",
        re.compile(
            r"(?i)(?:\bmkfs(?:\.[a-z0-9_-]+)?\b|\bwipefs\b|"
            r"\bdiskutil\s+(?:eraseDisk|partitionDisk|zeroDisk)\b|"
            r"\bformat(?:\.com)?\s+[a-z]:\b)"
        ),
    ),
    (
        "raw_disk_write",
        "EvolveTrace blocked a command that may write directly to a physical storage device.",
        re.compile(
            r"(?i)\bdd\b[^\n]*\bof=(?:/dev/(?:sd|nvme|vd|disk)[a-z0-9p]*|"
            r"\\\\\.\\physicaldrive\d+)"
        ),
    ),
    (
        "recursive_delete_escape",
        "EvolveTrace blocked recursive deletion outside the current project boundary.",
        re.compile(
            r"(?i)\brm\s+-[a-z]*(?:r[a-z]*f|f[a-z]*r)[a-z]*\s+"
            r"(?:/|~(?:/|$)|\.\.(?:/|$)|\$\{?home\}?(?:/|$))|"
            r"\b(?:remove-item|ri)\b(?=[^\n]*(?:-recurse|-r)\b)"
            r"(?=[^\n]*(?:-force|-f)\b)[^\n]*(?:[a-z]:\\|~\\|\.\.(?:\\|/|$))"
        ),
    ),
    (
        "remote_shell_pipeline",
        "EvolveTrace blocked downloading network content directly into a shell interpreter.",
        re.compile(
            r"(?i)\b(?:curl|wget|invoke-webrequest|iwr)\b[^|\n]*\|\s*"
            r"(?:sudo\s+)?(?:sh|bash|zsh|pwsh|powershell)(?:\s|$)"
        ),
    ),
)


def _command_from(payload: dict[str, Any]) -> str:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return ""
    return str(tool_input.get("command") or "")


def evaluate_pre_tool_use(payload: dict[str, Any]) -> SafetyDecision:
    if (
        payload.get("hook_event_name") != "PreToolUse"
        or payload.get("tool_name") != "Bash"
    ):
        return SafetyDecision("allow")

    command = _command_from(payload)
    for rule_id, reason, pattern in _RULES:
        if pattern.search(command):
            return SafetyDecision("deny", rule_id, reason)
    return SafetyDecision("allow")


def apply_safety_decision(
    payload: dict[str, Any], decision: SafetyDecision
) -> dict[str, Any]:
    prepared = dict(payload)
    prepared["safety"] = {
        "decision": decision.decision,
        "rule_id": decision.rule_id,
        "reason": decision.reason,
    }
    return prepared


def codex_hook_output(decision: SafetyDecision) -> dict[str, Any] | None:
    if not decision.denied:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": decision.reason,
        }
    }
