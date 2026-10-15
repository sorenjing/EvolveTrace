"""Bounded, deterministic command observations; never infer OS or disk health."""

from collections import Counter, defaultdict
from datetime import datetime
import hashlib
import re
import shlex

from .execution_results import execution_result


VERSION = "activity/v1"
CATEGORIES = ("read_search", "edit", "build_test", "dependencies", "git", "network", "mixed", "other")
WINDOW_SECONDS = 600
PHASES = {"PreToolUse", "PostToolUse", "PostToolUseFailure"}


def _command(event: dict) -> str:
    value = event.get("details", {}).get("tool_input", {})
    if isinstance(value, dict):
        return str(value.get("command") or value.get("cmd") or "")
    return value if isinstance(value, str) else ""


def _tokens(command: str) -> list[str]:
    try:
        # Used for classification only, never for command identity.
        return shlex.split(command, posix=False)
    except ValueError:
        return []


def _category(event: dict, command: str) -> str:
    tool = event.get("tool_name", "").split(".")[-1].lower()
    if tool in {"apply_patch", "edit", "write"}:
        return "edit"
    if tool in {"read", "glob", "grep", "read_file", "list_directory"}:
        return "read_search"
    tokens = _tokens(command)
    if not tokens:
        return "other"
    # Strip quoted strings before detecting shell operators. Compound scripts
    # remain one observed invocation, never imaginary executed subcommands.
    operators = re.sub(r'''"[^"\n]*"|'[^'\n]*' ''', "", command, flags=re.VERBOSE)
    if re.search(r"[;&|\n]", operators):
        return "mixed"
    executable = tokens[0].replace("\\", "/").rsplit("/", 1)[-1].lower().removesuffix(".exe")
    args = [value.lower() for value in tokens[1:]]
    if executable == "git":
        return "git"
    if executable in {"rg", "grep", "find", "ls", "dir", "cat", "head", "tail", "get-content", "get-childitem", "select-string"}:
        return "read_search"
    if executable in {"rm", "cp", "mv", "mkdir", "remove-item", "set-content", "add-content", "copy-item", "move-item", "new-item"}:
        return "edit"
    if executable in {"curl", "wget", "invoke-webrequest", "invoke-restmethod"}:
        return "network"
    if executable in {"npm", "pnpm", "yarn", "pip", "pip3", "uv", "poetry", "cargo", "go", "python", "python3"}:
        if any(value in {"install", "ci", "add", "update", "sync", "download", "uninstall"} for value in args[:3]):
            return "dependencies"
        if any(value in {"test", "build", "lint", "check", "pytest", "unittest", "compile", "vitest", "jest"} for value in args[:3]):
            return "build_test"
    if executable in {"pytest", "ruff", "eslint", "tsc", "make", "cmake", "msbuild", "dotnet"}:
        return "build_test"
    return "other"


def _time(value: object) -> float | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.timestamp() if parsed.tzinfo is not None else None
    except (ValueError, OverflowError, OSError):
        return None


def _denied(event: dict) -> bool:
    safety = event.get("details", {}).get("safety")
    return isinstance(safety, dict) and safety.get("decision") == "deny"


def ordered_events(events: list[dict]) -> list[dict]:
    return [event for _, event in sorted(enumerate(events), key=lambda pair: (
        pair[1]["sequence"] if isinstance(pair[1].get("sequence"), int) else pair[0], pair[0]))]


def command_attempts(events: list[dict]) -> list[dict]:
    calls, seen, epoch = {}, set(), defaultdict(int)
    for position, original in enumerate(ordered_events(events)):
        event = {"event_type": "PostToolUse", "session_id": "", **original}
        if event["event_id"] in seen:
            continue
        seen.add(event["event_id"])
        details = event.get("details", {})
        session = event["session_id"]
        if details.get("changed_files") or event.get("tool_name", "").lower() in {"apply_patch", "edit", "write"}:
            epoch[session] += 1
        if event["event_type"] not in PHASES or not event.get("tool_name") or _denied(event):
            continue
        call_id = details.get("tool_use_id")
        key = (session, str(call_id)) if call_id else (session, event["event_id"])
        command = _command(event)
        category = _category(event, command)
        attempt = calls.setdefault(key, {"session_id": session, "command": command,
                                        "category": category, "epoch": epoch[session], "refs": [],
                                        "cwd": event.get("cwd", ""), "has_call_id": bool(call_id), "has_start": False,
                                        "position": position, "tool_name": event.get("tool_name", ""),
                                        "start_position": position if "event_type" not in original else None,
                                        "start_time": None})
        if event["event_type"] == "PreToolUse":
            attempt["has_start"] = True
            attempt["start_position"] = position
            attempt["start_time"] = _time(event.get("timestamp"))
        if command and not attempt["command"]:
            attempt.update(command=command, category=category)
        attempt["refs"].append(event["event_id"])
        # Terminal evidence wins if delivery order is reversed.
        outcome = execution_result(event)
        known = {"success", "failure", "cancelled"}
        if (attempt.get("result_source") == "conflict" or outcome["source"] == "conflict"
                or (attempt.get("outcome") in known and outcome["outcome"] in known
                    and (attempt["outcome"] != outcome["outcome"] or
                         (attempt.get("exit") is not None and outcome["exit_code"] is not None and attempt["exit"] != outcome["exit_code"])))):
            outcome = {**outcome, "outcome": "unknown", "exit_code": None, "source": "conflict"}
        if outcome["outcome"] != "pending" or not attempt.get("terminal"):
            attempt["time"] = outcome["completed_at"] if outcome["completed_at"] is not None else _time(event.get("timestamp"))
            attempt["exit"] = outcome["exit_code"]
            attempt["outcome"] = outcome["outcome"]
            attempt["pending"] = outcome["outcome"] == "pending"
            attempt["failed"] = outcome["outcome"] == "failure"
            attempt["terminal"] = not attempt["pending"]
            attempt["duration"] = outcome["duration_ms"]
            attempt["result_source"] = outcome["source"]
            attempt["duration_source"] = outcome["duration_source"]
            attempt["end_position"] = position
            if outcome["started_at"] is not None:
                attempt["start_time"] = outcome["started_at"]
        if category == "edit":
            epoch[session] += 1
    return list(calls.values())


def _fingerprint(attempt: dict) -> str | None:
    command = attempt["command"]
    if not command or "[REDACTED]" in command or len(command) > 65536:
        return None
    tokens = _tokens(command)
    if not tokens:
        return None
    # Preserve attached quoted arguments and escapes exactly. A conservative
    # textual identity can miss harmless formatting variants but cannot merge
    # distinct search patterns by collapsing whitespace inside their quotes.
    return hashlib.sha256((attempt["cwd"] + "\0" + command.strip()).encode()).hexdigest()[:24]


def analyze_activity(events: list[dict]) -> dict:
    attempts = command_attempts(events)
    categories = Counter(item["category"] for item in attempts)
    sessions = defaultdict(list)
    for attempt in attempts:
        sessions[attempt["session_id"]].append(attempt)
    findings = []
    for session_id, calls in sessions.items():
        times = [item["time"] for item in calls if item.get("time") is not None]
        if not times:
            continue
        end = max(times)
        repeated, failures = defaultdict(list), defaultdict(list)
        for item in calls:
            fingerprint = _fingerprint(item)
            if fingerprint is None:
                continue
            retry_key = (fingerprint, item["category"])
            timed = item.get("time") is not None and end - WINDOW_SECONDS <= item["time"] <= end
            if not timed or item["pending"]:
                # Untimed outcomes cannot supply finding evidence, but observed
                # success/unknown outcomes still interrupt a claimed streak.
                failures[retry_key] = []
                continue
            repeated[(fingerprint, item["epoch"], item["category"])].append(item)
            if item["failed"]:
                failures[retry_key].append(item)
            else:
                failures[retry_key] = []
        candidates = {}
        for (fingerprint, category), group in failures.items():
            if len(group) >= 3:
                candidates[(fingerprint, category)] = ("failed_retry", group)
        for key, group in repeated.items():
            fingerprint, _, category = key
            existing = candidates.get((fingerprint, category))
            if existing and existing[0] == "failed_retry":
                continue
            if len(group) >= 5 and category in {"read_search", "build_test"}:
                code = "repeated_read" if category == "read_search" else "repeated_build"
                # One current suggestion per session/command/rule; later edit
                # epochs must not produce duplicate IDs or UI keys.
                candidates[(fingerprint, category)] = (code, group)
        for (fingerprint, category), (code, evidence) in candidates.items():
            refs = list(dict.fromkeys(ref for item in evidence for ref in item["refs"]))
            identity = f"{VERSION}:{session_id}:{code}:{fingerprint}"
            findings.append({"finding_id": hashlib.sha256(identity.encode()).hexdigest()[:32],
                             "session_id": session_id, "code": code, "category": category,
                             "count": len(evidence), "window_seconds": WINDOW_SECONDS,
                             "evidence_refs": refs[-20:], "rule_version": VERSION,
                             "summary": "Repeated observed failures" if code == "failed_retry" else "Repeated operations without captured edit evidence",
                             "requires_review": True})
    durations = [item["duration"] for item in attempts if item.get("duration") is not None]
    unpaired = sum(not item["has_call_id"] for item in attempts)
    orphaned = sum(item["has_call_id"] and item["terminal"] and not item["has_start"] for item in attempts)
    denied = len({event["event_id"] for event in events if _denied(event)})
    return {"schema_version": VERSION, "attempt_count": len(attempts),
            "unpaired_event_count": unpaired, "orphan_completion_count": orphaned,
            "coverage": "incomplete_pairing" if unpaired or orphaned else "captured_hook_events_only",
            "denied_count": denied,
            "categories": {key: categories[key] for key in CATEGORIES},
            "failed_count": sum(item["failed"] for item in attempts),
            "success_count": sum(item["outcome"] == "success" for item in attempts),
            "cancelled_count": sum(item["outcome"] == "cancelled" for item in attempts),
            "pending_count": sum(item["pending"] for item in attempts),
            "unknown_outcome_count": sum(item["outcome"] == "unknown" for item in attempts),
            "result_sample_count": sum(item["outcome"] in {"success", "failure", "cancelled"} for item in attempts),
            "result_sources": {source: sum(item["result_source"] == source for item in attempts) for source in ("hook", "execution_record", "unknown", "conflict")},
            "duration_sources": {source: sum(item["duration_source"] == source for item in attempts) for source in ("hook", "execution_record", "unknown")},
            "reported_duration_ms": sum(durations), "duration_sample_count": len(durations),
            "resource_metrics": "not_collected", "hardware_health": "not_collected", "findings": findings}
