"""Typed command outcomes; never infer an exit code from output text."""

import math

from .command_classification import expected_nonzero

def number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return float(value) if math.isfinite(value) and value >= 0 else None
        except (ValueError, OverflowError):
            pass
    return None


def _code(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _outcome(code: int | None, status: object) -> str:
    status = status.lower() if isinstance(status, str) else ""
    if status in {"cancelled", "canceled", "aborted", "interrupted"}:
        return "cancelled"
    if status in {"failed", "failure", "error"}:
        return "failure" if code != 0 else "unknown"
    return "unknown" if code is None else "success" if code == 0 else "failure"


def completed_result(item: dict, payload: dict) -> dict:
    code = _code(item.get("exit_code"))
    outcome = _outcome(code, item.get("status"))
    duration = item.get("duration")
    milliseconds = None
    if isinstance(duration, dict):
        seconds, nanos = number(duration.get("secs")), number(duration.get("nanos"))
        if seconds is not None and nanos is not None and nanos < 1000000000:
            milliseconds = number(seconds * 1000 + nanos / 1000000)
    start, end = number(payload.get("started_at_ms")), number(payload.get("completed_at_ms"))
    if start is None or end is None or start > end:
        start = end = None
    return {"outcome": outcome, "exit_code": code if outcome != "unknown" else None,
            "duration_ms": milliseconds, "started_at": start / 1000 if start is not None else None,
            "completed_at": end / 1000 if end is not None else None}


def execution_result(event: dict) -> dict:
    details = event.get("details", {})
    response = details.get("tool_response")
    response = response if isinstance(response, dict) else {}
    pre = event.get("event_type") == "PreToolUse"
    code = _code(details.get("exit_code"))
    if code is None:
        code = _code(response.get("exit_code"))
    code = None if pre else code
    status = details.get("status")
    if not isinstance(status, str):
        status = response.get("status")
    outcome = "pending" if pre else _outcome(code, status)
    if event.get("event_type") == "PostToolUseFailure" and outcome != "cancelled":
        outcome = "failure"
    duration = number(details.get("duration_ms"))
    if duration is None:
        duration = number(response.get("duration_ms"))
    duration = None if pre else duration
    source = "hook" if outcome in {"success", "failure", "cancelled"} else "unknown"
    duration_source = "hook" if duration is not None else "unknown"
    metadata = event.get("_execution_result")
    if isinstance(metadata, dict):
        other = metadata["outcome"]
        if outcome in {"success", "failure", "cancelled"} and other in {"success", "failure", "cancelled"} and (outcome != other or (code is not None and metadata["exit_code"] is not None and code != metadata["exit_code"])):
            outcome, code, source = "unknown", None, "conflict"
        elif source == "unknown":
            outcome, code = other, metadata["exit_code"]
            source = "execution_record" if other != "unknown" else "unknown"
        if duration is None and metadata["duration_ms"] is not None:
            duration, duration_source = metadata["duration_ms"], "execution_record"
        if metadata.get("conflict") is True:
            outcome, code, source = "unknown", None, "conflict"
    tool_input = details.get("tool_input", {})
    command = tool_input.get("command") or tool_input.get("cmd") if isinstance(tool_input, dict) else tool_input
    query_result = None
    if (outcome == "failure" and code == 1 and source != "conflict"
            and event.get("event_type") != "PostToolUseFailure"
            and (not isinstance(status, str) or status.lower() not in {"failed", "failure", "error"})
            and isinstance(command, str)):
        query_result = expected_nonzero(event.get("tool_name", ""), command)
    return {"outcome": outcome, "exit_code": code, "duration_ms": duration, "query_result": query_result,
            "source": source, "duration_source": duration_source,
            "started_at": metadata.get("started_at") if isinstance(metadata, dict) else None,
            "completed_at": metadata.get("completed_at") if isinstance(metadata, dict) else None}
