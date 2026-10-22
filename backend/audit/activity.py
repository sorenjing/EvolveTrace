"""Bounded, deterministic command observations; never infer OS or disk health."""

from collections import Counter, defaultdict
from datetime import datetime
import hashlib

from .command_classification import VERSION as CLASSIFICATION_VERSION, classify_command, tokens as _tokens
from .execution_results import execution_result


VERSION = "activity/v1"
RULE_VERSION = "activity/v2"
CATEGORIES = ("read_search", "edit", "build_test", "dependencies", "git", "network", "mixed", "other")
WINDOW_SECONDS = 600
REPEATED_OPERATION_MIN = 5
FAILED_RETRY_MIN = 3
PHASES = {"PreToolUse", "PostToolUse", "PostToolUseFailure"}


def rule_policy() -> dict:
    return {"version": RULE_VERSION, "window_seconds": WINDOW_SECONDS,
            "repeated_operation_min": REPEATED_OPERATION_MIN, "failed_retry_min": FAILED_RETRY_MIN,
            "window_anchor": "latest_observed_call_per_session", "calibration": "heuristic"}


def _command(event: dict) -> str:
    value = event.get("details", {}).get("tool_input", {})
    if isinstance(value, dict):
        return str(value.get("command") or value.get("cmd") or "")
    return value if isinstance(value, str) else ""


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
        classification = classify_command(event.get("tool_name", ""), command)
        category = classification["category"]
        attempt = calls.setdefault(key, {"session_id": session, "command": command,
                                        "category": category, "classification": classification, "epoch": epoch[session], "refs": [],
                                        "cwd": event.get("cwd", ""), "has_call_id": bool(call_id), "has_start": False,
                                        "position": position, "tool_name": event.get("tool_name", ""),
                                        "start_position": position if "event_type" not in original else None,
                                        "start_time": None})
        if event["event_type"] == "PreToolUse":
            attempt["has_start"] = True
            attempt["start_position"] = position
            attempt["start_time"] = _time(event.get("timestamp"))
        if command and not attempt["command"]:
            attempt.update(command=command, category=category, classification=classification)
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
            attempt["query_result"] = outcome.get("query_result") if outcome["source"] != "conflict" else None
            attempt["terminal"] = not attempt["pending"]
            attempt["duration"] = outcome["duration_ms"]
            attempt["result_source"] = outcome["source"]
            attempt["duration_source"] = outcome["duration_source"]
            attempt["_outcome_event"] = event
            attempt["end_position"] = position
            if outcome["started_at"] is not None:
                attempt["start_time"] = outcome["started_at"]
        if classification["operation"] == "modify_files":
            epoch[session] += 1
    attempts = list(calls.values())
    for attempt in attempts:
        terminal = attempt.pop("_outcome_event", None)
        if (terminal and attempt["has_call_id"] and attempt.get("failed")
                and attempt.get("result_source") != "conflict" and attempt["command"] and not _command(terminal)):
            # Delivery may be reversed. Borrow only the same call's observed
            # command for interpretation; never rewrite stored evidence or exits.
            projected = {**terminal, "details": {**terminal.get("details", {}), "tool_input": {"command": attempt["command"]}}}
            attempt["query_result"] = execution_result(projected).get("query_result")
    return attempts


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
            if item["failed"] and not item.get("query_result"):
                failures[retry_key].append(item)
            else:
                failures[retry_key] = []
        candidates = {}
        for (fingerprint, category), group in failures.items():
            if len(group) >= FAILED_RETRY_MIN:
                candidates[(fingerprint, category)] = ("failed_retry", group)
        for key, group in repeated.items():
            fingerprint, _, category = key
            existing = candidates.get((fingerprint, category))
            if existing and existing[0] == "failed_retry":
                continue
            if len(group) >= REPEATED_OPERATION_MIN and category in {"read_search", "build_test"}:
                code = "repeated_read" if category == "read_search" else "repeated_build"
                # One current suggestion per session/command/rule; later edit
                # epochs must not produce duplicate IDs or UI keys.
                candidates[(fingerprint, category)] = (code, group)
        for (fingerprint, category), (code, evidence) in candidates.items():
            refs = list(dict.fromkeys(ref for item in evidence for ref in item["refs"]))
            identity = f"{RULE_VERSION}:{session_id}:{code}:{fingerprint}"
            findings.append({"finding_id": hashlib.sha256(identity.encode()).hexdigest()[:32],
                             "session_id": session_id, "code": code, "category": category,
                             "count": len(evidence), "window_seconds": WINDOW_SECONDS,
                             "evidence_refs": refs[-20:], "rule_version": RULE_VERSION,
                             "summary": "Repeated observed failures" if code == "failed_retry" else "Repeated operations without captured edit evidence",
                             "requires_review": True})
    durations = [item["duration"] for item in attempts if item.get("duration") is not None]
    unpaired = sum(not item["has_call_id"] for item in attempts)
    orphaned = sum(item["has_call_id"] and item["terminal"] and not item["has_start"] for item in attempts)
    denied = len({event["event_id"] for event in events if _denied(event)})
    operations = defaultdict(list)
    for item in attempts:
        operations[item["classification"]["operation"]].append(item)
    breakdown = []
    for operation, items in sorted(operations.items()):
        samples = [item["duration"] for item in items if item.get("duration") is not None]
        breakdown.append({"operation": operation, "count": len(items),
            **{f"{key}_count": sum(item["outcome"] == value for item in items) for key, value in
               (("success", "success"), ("failed", "failure"), ("unknown_outcome", "unknown"), ("pending", "pending"), ("cancelled", "cancelled"))},
            "expected_nonzero_count": sum(bool(item.get("query_result")) for item in items),
            "duration_sample_count": len(samples), "reported_duration_ms": sum(samples),
            "inferred_count": sum(item["classification"]["basis"] in {"script_name_hint", "compound_hint"} for item in items)})
    return {"schema_version": VERSION, "attempt_count": len(attempts),
            "classification_version": CLASSIFICATION_VERSION, "operations": breakdown,
            "command_shapes": {shape: sum(item["classification"]["shape"] == shape for item in attempts) for shape in ("single", "compound", "tool")},
            "expected_nonzero_count": sum(bool(item.get("query_result")) for item in attempts),
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
