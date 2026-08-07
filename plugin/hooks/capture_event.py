import json
import os
import re
import sys
import urllib.request
from typing import Any


REDACTED = "[REDACTED]"
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|passwd|"
    r"secret|authorization|cookie|credential|private[_-]?key|client[_-]?secret)",
    re.IGNORECASE,
)
BEARER_PATTERN = re.compile(r"(?i)(\bbearer\s+)[^\s,;'\\\"]+")
AUTH_SCHEME_PATTERN = re.compile(r"(?i)\b(Basic|Bearer)\s+[^\s,;'\" ]+")
HEADER_VALUE_PATTERN = re.compile(
    r"(?i)\b((?:authorization|proxy-authorization|cookie|set-cookie|"
    r"x-[a-z0-9_-]*(?:token|key|secret|auth)[a-z0-9_-]*)\s*:\s*)[^\r\n]+"
)
URL_QUERY_PATTERN = re.compile(
    r"(?i)([?&](?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|"
    r"password|passwd|secret|key)=)[^&#\s]+"
)
JWT_PATTERN = re.compile(
    r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"
)
RAW_SECRET_PATTERN = re.compile(
    r"\b(?:sk-(?:proj|live|test)-[A-Za-z0-9_-]{10,}|gh[pousr]_[A-Za-z0-9]{10,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}|AIza[A-Za-z0-9_-]{20,}|npm_[A-Za-z0-9]{10,})\b"
)
ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|"
    r"secret|authorization)\s*([=:])\s*([^\s,;]+)"
)


def redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED if SENSITIVE_KEY_PATTERN.search(str(key)) else redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, str):
        value = HEADER_VALUE_PATTERN.sub(r"\1" + REDACTED, value)
        value = AUTH_SCHEME_PATTERN.sub(r"\1 " + REDACTED, value)
        value = URL_QUERY_PATTERN.sub(r"\1" + REDACTED, value)
        value = BEARER_PATTERN.sub(r"\1" + REDACTED, value)
        value = ASSIGNMENT_PATTERN.sub(r"\1\2" + REDACTED, value)
        value = JWT_PATTERN.sub(REDACTED, value)
        return RAW_SECRET_PATTERN.sub(REDACTED, value)
    return value


def capture(payload: dict[str, Any], endpoint: str | None = None) -> bool:
    if not isinstance(payload, dict):
        return False
    if not str(payload.get("session_id") or "").strip():
        return False
    if not str(
        payload.get("hook_event_name") or payload.get("event_type") or payload.get("type") or ""
    ).strip():
        return False

    url = endpoint or os.getenv("EVOLVETRACE_API_URL", "http://127.0.0.1:8001/api/audit/events")
    request = urllib.request.Request(
        url,
        data=json.dumps(redact_value(payload), ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=1.5)
    except Exception:
        return False
    return True


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        capture(payload)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
