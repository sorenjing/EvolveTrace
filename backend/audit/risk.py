import re
from dataclasses import asdict, dataclass
from typing import Any

from .models import AuditEvent
from .execution_results import execution_result


@dataclass(frozen=True)
class RiskFinding:
    event_id: str
    code: str
    severity: str
    message: str
    evidence: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


DANGEROUS_COMMANDS = (
    re.compile(r"(?i)\brm\s+-[^\n]*\brf\b"),
    re.compile(r"(?i)\bgit\s+reset\s+--hard\b"),
    re.compile(r"(?i)\bgit\s+clean\s+-[^\n]*f"),
    re.compile(r"(?i)\bcurl\b[^\n|]*\|\s*(?:ba)?sh\b"),
    re.compile(r"(?i)\b(?:sudo|shutdown|format)\b"),
    re.compile(r"(?i)\bdel\s+/[fqs][^\n]*\b"),
)


def _flatten_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(f"{key} {_flatten_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text(item) for item in value)
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return ""


def _tool_response_failed(event: AuditEvent) -> bool:
    result = execution_result(event.to_dict())
    return result["outcome"] == "failure" and not result.get("query_result")


def _safety_block(event: AuditEvent) -> RiskFinding | None:
    safety = event.details.get("safety")
    if not isinstance(safety, dict) or safety.get("decision") != "deny":
        return None
    rule_id = str(safety.get("rule_id") or "")
    return RiskFinding(
        event_id=event.event_id,
        code="safety_block",
        severity="high",
        message="Safety Sentinel blocked this tool call before execution.",
        evidence=rule_id,
    )


def analyze_event(event: AuditEvent) -> list[RiskFinding]:
    findings: list[RiskFinding] = []
    safety_block = _safety_block(event)
    if safety_block is not None:
        findings.append(safety_block)

    command_text = _flatten_text(event.details)
    for pattern in DANGEROUS_COMMANDS:
        match = pattern.search(command_text)
        if match:
            findings.append(
                RiskFinding(
                    event_id=event.event_id,
                    code="dangerous_command",
                    severity="high",
                    message="工具调用包含高风险命令。",
                    evidence=match.group(0),
                )
            )
            break

    if any(
        bool(event.details.get(key))
        for key in ("permission_denied", "permissionDenied", "permission_denied_reason")
    ):
        findings.append(
            RiskFinding(
                event_id=event.event_id,
                code="permission_denied",
                severity="medium",
                message="工具调用被权限策略拒绝。",
            )
        )

    if event.event_type in {"PostToolUse", "PostToolUseFailure"} and _tool_response_failed(event):
        findings.append(
            RiskFinding(
                event_id=event.event_id,
                code="tool_failure",
                severity="medium",
                message="观察到非零退出或失败状态，请结合命令含义核对。",
            )
        )
    return findings
