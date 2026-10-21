import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request
from typing import Any


HOOKS_DIR = Path(__file__).resolve().parent
if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))

from safety_policy import apply_safety_decision, codex_hook_output, evaluate_pre_tool_use


REDACTED = "[REDACTED]"
SENSITIVE_KEY_PATTERN = re.compile(
    r"(?:api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|passwd|"
    r"secret|authorization|cookie|credential|private[_-]?key|client[_-]?secret)",
    re.IGNORECASE,
)
BEARER_PATTERN = re.compile(r"(?i)(\bbearer\s+)[^\s,;'\\\"]+")
AUTH_SCHEME_PATTERN = re.compile(r"(?i)\b(Basic|Bearer)\s+[^\s,;'\"]+")
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
    r"token|secret|authorization)\s*([=:])\s*([^\s,;]+)"
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
    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(redact_value(payload), ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(request, timeout=1.5)
    except Exception:
        return False
    return True


def process_payload(payload: dict[str, Any]) -> int:
    decision = evaluate_pre_tool_use(payload)
    hook_output = codex_hook_output(decision)
    if hook_output is not None:
        print(json.dumps(hook_output, ensure_ascii=False), flush=True)

    # Best-effort telemetry must not discard a local policy decision.
    try:
        captured = apply_safety_decision(payload, decision)
        if payload.get("hook_event_name") in {"SessionStart", "SessionEnd"}:
            captured = {**captured, "repository_state": repository_state(payload.get("cwd"))}
        capture(captured)
    except Exception:
        pass
    return 0


def repository_state(cwd: object) -> dict:
    """Bounded Git observation; never capture source contents or scan untracked files."""
    state = {"schema_version": "repository-state/v1", "authority": "client_collected_git",
             "coverage": "tracked_files_only", "head_commit": None, "tracked_dirty": None}
    if not isinstance(cwd, str) or not Path(cwd).is_absolute():
        return state
    command = ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "-C", cwd]
    try:
        head = subprocess.run([*command, "rev-parse", "--verify", "HEAD"], stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, timeout=0.4)
        revision = head.stdout.strip()
        if head.returncode or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
            return state
        dirty = subprocess.run([*command, "diff", "--quiet", "--no-ext-diff", "--no-textconv", "HEAD", "--"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=0.4)
        if dirty.returncode in {0, 1}:
            state.update(head_commit=revision, tracked_dirty=bool(dirty.returncode))
    except (OSError, subprocess.TimeoutExpired):
        pass
    return state


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if isinstance(payload, dict):
            return process_payload(payload)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
