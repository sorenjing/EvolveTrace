import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit.activity import analyze_activity


def event(index, command="rg pattern src", phase="PostToolUse", *, call=None, exit_code=0, **details):
    return {"event_id": f"e-{index}", "session_id": "s-1", "event_type": phase,
            "timestamp": (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=index)).isoformat(),
            "sequence": index, "cwd": "/workspace/demo", "tool_name": "Bash",
            "details": {"tool_use_id": call, "tool_input": {"command": command},
                        "tool_response": {"exit_code": exit_code}, **details}}


def test_pairs_once_and_preserves_unpaired_calls():
    result = analyze_activity([event(1, phase="PreToolUse", call="a"), event(2, call="a"),
                               event(3, phase="PreToolUse", call="b"), event(4)])
    assert result["attempt_count"] == 3
    assert result["categories"]["read_search"] == 3
    assert result["pending_count"] == 1
    assert result["failed_count"] == 0


def test_repeated_read_rule_has_evidence_but_no_disk_claim():
    result = analyze_activity([event(i) for i in range(5)])
    finding = result["findings"][0]
    assert finding["code"] == "repeated_read"
    assert finding["evidence_refs"] == [f"e-{i}" for i in range(5)]
    assert result["resource_metrics"] == "not_collected"
    assert result["hardware_health"] == "not_collected"


def test_captured_edit_and_long_gap_break_repetition():
    edited = event(3, command="", changed_files=["src/example.py"])
    edited["tool_name"] = "apply_patch"
    assert analyze_activity([event(i) for i in range(3)] + [edited] + [event(i) for i in range(4, 7)])["findings"] == []
    assert analyze_activity([event(i * 601) for i in range(5)])["findings"] == []


def test_success_breaks_failed_retry_streak_and_missing_outcome_is_unknown():
    failures = [event(i, "npm run build", exit_code=1) for i in range(3)]
    assert analyze_activity(failures)["findings"][0]["code"] == "failed_retry"
    assert analyze_activity(failures[:2] + [event(3, "npm run build")] + [event(4, "npm run build", exit_code=1)])["findings"] == []
    missing = event(1, tool_response={})
    assert analyze_activity([missing])["unknown_outcome_count"] == 1


def test_quotes_compound_commands_redaction_and_missing_timestamps():
    distinct = [event(i, f'rg "{"a  b" if i % 2 else "a b"}" src') for i in range(8)]
    assert analyze_activity(distinct)["findings"] == []
    assert analyze_activity([event(1, "rg x src && npm test")])["categories"]["mixed"] == 1
    assert analyze_activity([event(i, "rg [REDACTED] src") for i in range(6)])["findings"] == []
    untimed = [dict(event(i), timestamp="invalid") for i in range(6)]
    assert analyze_activity(untimed)["findings"] == []


def test_duplicate_events_and_sessions_do_not_merge_and_duration_is_explicit():
    first = event(1, call="same", duration_ms=12)
    second = dict(event(2, call="same"), session_id="s-2")
    result = analyze_activity([first, first, second])
    assert result["attempt_count"] == 2
    assert result["reported_duration_ms"] == 12
    assert result["duration_sample_count"] == 1


def test_same_command_in_distinct_directories_and_denials_are_not_retries():
    calls = [dict(event(i, "npm run build"), cwd=f"/workspace/demo/sub-{i}") for i in range(6)]
    assert analyze_activity(calls)["findings"] == []
    denied = [event(i, "rg x src", phase="PreToolUse", safety={"decision": "deny"}) for i in range(5)]
    result = analyze_activity(denied)
    assert result["attempt_count"] == 0
    assert result["denied_count"] == 5


def test_bare_pre_and_post_without_ids_are_explicitly_incomplete():
    result = analyze_activity([event(1, phase="PreToolUse"), event(2)])
    assert result["unpaired_event_count"] == 2
    assert result["coverage"] == "incomplete_pairing"


def test_optional_hook_details_can_be_malformed_without_breaking_reports():
    assert analyze_activity([event(1, safety="unavailable")])["attempt_count"] == 1


def test_attached_quoted_arguments_preserve_distinct_searches():
    calls = [event(i, 'rg --regexp="a b" src' if i % 2 else 'rg --regexp="a  b" src') for i in range(8)]
    assert analyze_activity(calls)["findings"] == []


def test_edits_do_not_hide_repeated_failure_of_the_same_command():
    edit = event(2, "", changed_files=["src/example.py"])
    edit["tool_name"] = "apply_patch"
    calls = [event(1, "npm run build", exit_code=1), edit,
             event(3, "npm run build", exit_code=1), event(4, "npm run build", exit_code=1)]
    assert analyze_activity(calls)["findings"][0]["code"] == "failed_retry"


def test_untimed_success_is_still_a_failure_streak_barrier():
    calls = [event(1, "npm run build", exit_code=1),
             dict(event(2, "npm run build"), timestamp="invalid"),
             event(3, "npm run build", exit_code=1), event(4, "npm run build", exit_code=1)]
    assert analyze_activity(calls)["findings"] == []


def test_completion_with_id_but_missing_start_reports_a_coverage_gap():
    result = analyze_activity([event(1, call="only-completion")])
    assert result["orphan_completion_count"] == 1
    assert result["coverage"] == "incomplete_pairing"
