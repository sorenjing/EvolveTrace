from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import re
from typing import Any
from uuid import uuid4

from .redaction import redact_value


CORE_FIELDS = {
    "event_id",
    "id",
    "session_id",
    "turn_id",
    "sequence",
    "hook_event_name",
    "event_type",
    "type",
    "timestamp",
    "created_at",
    "cwd",
    "project_path",
    "tool_name",
}
PATCH_FILE_PATTERN = re.compile(
    r"^\*\*\*\s+(?:Update|Add|Delete)\s+File:\s*(.+?)\s*$", re.MULTILINE
)


def _stable_event_id(payload: dict[str, Any], event_type: str) -> str | None:
    tool_use_id = str(payload.get("tool_use_id") or "").strip()
    session_id = str(payload.get("session_id") or "").strip()
    if not tool_use_id or not session_id:
        return None
    identity = f"{session_id}\0{tool_use_id}\0{event_type}".encode("utf-8")
    return f"tool-{hashlib.sha256(identity).hexdigest()}"


def _derive_changed_files(tool_name: str, details: dict[str, Any]) -> list[str]:
    if tool_name not in {"apply_patch", "Edit", "Write"}:
        return []
    tool_input = details.get("tool_input")
    if isinstance(tool_input, dict):
        patch_text = "\n".join(
            str(tool_input.get(key) or "") for key in ("command", "patch", "input")
        )
    else:
        patch_text = str(tool_input or "")
    files: list[str] = []
    for path in PATCH_FILE_PATTERN.findall(patch_text):
        if path not in files:
            files.append(path)
    return files


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    session_id: str
    event_type: str
    timestamp: str
    turn_id: str
    sequence: int
    cwd: str
    tool_name: str
    details: dict[str, Any]

    @classmethod
    def from_hook(cls, payload: dict[str, Any]) -> "AuditEvent":
        if not isinstance(payload, dict):
            raise ValueError("hook payload must be an object")

        session_id = str(payload.get("session_id") or "").strip()
        if not session_id:
            raise ValueError("session_id is required")

        event_type = str(
            payload.get("hook_event_name") or payload.get("event_type") or payload.get("type") or ""
        ).strip()
        if not event_type:
            raise ValueError("event type is required")

        timestamp = str(
            payload.get("timestamp")
            or payload.get("created_at")
            or datetime.now(timezone.utc).isoformat()
        )
        sequence = payload.get("sequence", 0)
        try:
            sequence = int(sequence)
        except (TypeError, ValueError):
            raise ValueError("sequence must be an integer") from None

        details = {
            key: redact_value(value)
            for key, value in payload.items()
            if key not in CORE_FIELDS and key != "raw_payload"
        }
        tool_name = str(payload.get("tool_name") or "")
        changed_files = _derive_changed_files(tool_name, details)
        if changed_files and "changed_files" not in details:
            details["changed_files"] = changed_files
        return cls(
            event_id=str(
                payload.get("event_id")
                or payload.get("id")
                or _stable_event_id(payload, event_type)
                or uuid4()
            ),
            session_id=session_id,
            event_type=event_type,
            timestamp=timestamp,
            turn_id=str(payload.get("turn_id") or ""),
            sequence=sequence,
            cwd=str(payload.get("cwd") or payload.get("project_path") or ""),
            tool_name=tool_name,
            details=details,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
