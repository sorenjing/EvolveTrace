"""Bounded local execution-directory evidence, without importing chat content."""

import json
import os
import stat
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import url2pathname

from .execution_results import completed_result


FILE_LIMIT = 4
TAIL_BYTES = 1024 * 1024
HEADER_BYTES = 64 * 1024


def _local_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value or len(value) > 4096 or "\x00" in value:
        return None
    try:
        if value.startswith("file:"):
            uri = urlsplit(value)
            if uri.netloc not in {"", "localhost"} or uri.query or uri.fragment:
                return None
            value = url2pathname(uri.path)
        # Codex on Windows supplies extended-length paths; pathlib otherwise
        # treats these as a different drive from the configured sessions root.
        if os.name == "nt" and value.startswith("\\\\?\\"):
            value = value[4:]
        if value.startswith(("\\\\", "//")):
            return None
        path = Path(value)
        return path.resolve() if path.is_absolute() else None
    except (OSError, ValueError):
        return None


def _json_object(line: bytes) -> dict:
    try:
        value = json.loads(line)
        return value if isinstance(value, dict) else {}
    except (ValueError, UnicodeDecodeError, RecursionError):
        return {}


def _completed_directories(events: list[dict]) -> tuple[dict, dict]:
    root = (Path(os.getenv("CODEX_HOME", str(Path.home() / ".codex"))) / "sessions").resolve()
    requested: dict[tuple[str, Path], set[str]] = {}
    paths: dict[str, Path | None] = {}
    for event in reversed(events):
        details = event.get("details", {})
        call = details.get("tool_use_id")
        if not isinstance(event.get("session_id"), str) or not event["session_id"]:
            continue
        if event.get("tool_name", "").split(".")[-1].lower() not in {"bash", "shell", "exec_command"} or not isinstance(call, str) or not call:
            continue
        raw_path = details.get("transcript_path")
        if not isinstance(raw_path, str):
            continue
        if raw_path not in paths:
            paths[raw_path] = _local_path(raw_path)
        path = paths[raw_path]
        if path and path.suffix == ".jsonl" and path.is_relative_to(root):
            requested.setdefault((event["session_id"], path), set()).add(call)
    found = {}
    scan = {"files_read": 0, "file_limit": FILE_LIMIT, "tail_byte_limit": TAIL_BYTES,
            "limited": len(requested) > FILE_LIMIT}
    for (session, path), calls in list(requested.items())[:FILE_LIMIT]:
        try:
            if not stat.S_ISREG(path.stat().st_mode):
                continue
            with path.open("rb") as handle:
                header = _json_object(handle.readline(HEADER_BYTES))
                meta = header.get("payload")
                if header.get("type") != "session_meta" or not isinstance(meta, dict) or meta.get("id") != session:
                    continue
                handle.seek(0, 2)
                size = handle.tell()
                offset = max(0, size - TAIL_BYTES)
                handle.seek(offset)
                lines = handle.read(TAIL_BYTES).splitlines()
            scan["files_read"] += 1
            scan["limited"] |= bool(offset)
        except (OSError, ValueError):
            continue
        for line in lines[1:] if offset else lines:
            # Discard all message/reasoning records before JSON decoding. Only
            # directory metadata from the named completed call may be returned.
            if b'"item_completed"' not in line or b'"CommandExecution"' not in line:
                continue
            record = _json_object(line)
            payload = record.get("payload")
            if record.get("type") != "event_msg" or not isinstance(payload, dict) or payload.get("type") != "item_completed" or payload.get("thread_id") != session:
                continue
            item = payload.get("item")
            if not isinstance(item, dict) or item.get("type") != "CommandExecution" or not isinstance(item.get("id"), str) or item["id"] not in calls:
                continue
            cwd = _local_path(item.get("cwd"))
            if cwd is not None:
                key = (session, item["id"])
                evidence = {"cwd": str(cwd), "result": completed_result(item, payload)}
                found[key] = evidence if key not in found or found[key] == evidence else None
    return found, scan


def resolve_directories(events: list[dict]) -> tuple[list[dict], dict]:
    completed, scan = _completed_directories(events)
    result = []
    for event in events:
        details = event.get("details", {})
        call = details.get("tool_use_id")
        key = (event.get("session_id", ""), call) if isinstance(call, str) else None
        tool_input = details.get("tool_input")
        if key in completed:
            evidence, source = completed[key], "execution_record"
            directory = evidence["cwd"] if evidence is not None else ""
        elif isinstance(tool_input, dict) and ("workdir" in tool_input or "cwd" in tool_input):
            cwd = _local_path(tool_input.get("workdir", tool_input.get("cwd")))
            directory, source = (str(cwd) if cwd is not None else ""), "tool_workdir"
        else:
            directory, source = event.get("cwd", ""), "hook_cwd"
        resolved = {**event, "cwd": directory, "_directory_source": source}
        if key in completed and completed[key] is not None:
            resolved["_execution_result"] = completed[key]["result"]
        result.append(resolved)
    return result, scan
