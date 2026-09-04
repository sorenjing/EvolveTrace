import re
from dataclasses import asdict, dataclass
from typing import Any

from .models import AuditEvent


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


def _tool_response_failed(response: Any) -> bool:
    if isinstance(response, dict):
        status = str(response.get("status") or "").lower()
        if status in {"failed", "failure", "error"}:
            return True
        exit_code = response.get("exit_code", response.get("exitCode", response.get("returncode")))
        try:
            if exit_code is not None and int(exit_code) != 0:
                return True
        except (TypeError, ValueError):
            pass
        return bool(response.get("error"))
    text = str(response or "").lower()
    return bool(re.search(r"\b(?:error|failed|exit(?:ed)?\s+with\s+code\s+[1-9])\b", text))


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

    status = str(event.details.get("status") or event.details.get("result") or "").lower()
    failed = status in {"failed", "failure", "error"} or _tool_response_failed(
        event.details.get("tool_response")
    )
    if event.event_type in {"PostToolUse", "PostToolUseFailure"} and failed:
        findings.append(
            RiskFinding(
                event_id=event.event_id,
                code="tool_failure",
                severity="medium",
                message="工具调用返回失败结果。",
            )
        )
    return findings
