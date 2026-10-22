import pytest

from audit.activity import analyze_activity, command_attempts
from audit.models import AuditEvent
from audit.risk import analyze_event
from test_activity import event


@pytest.mark.parametrize("command,category,operation,basis", [
    ("rg --files", "read_search", "find_files", "known_command"),
    ("rg TODO src", "read_search", "search_content", "known_command"),
    ("Get-Content README.md", "read_search", "read_file", "known_command"),
    ("find . -delete", "edit", "modify_files", "known_command"),
    ("find . -exec custom {} ;", "mixed", "unknown", "unrecognized"),
    ("sed -i s/old/new/ src/a.py", "edit", "modify_files", "known_command"),
    ("sed -n 1,20p src/a.py", "read_search", "read_file", "known_command"),
    ("npm run site:build", "build_test", "build_package", "script_name_hint"),
    ("npm run test:unit", "build_test", "verify_tests", "script_name_hint"),
    ("npm run typecheck", "build_test", "verify_static", "script_name_hint"),
    ("npm run security:deps", "build_test", "verify_static", "script_name_hint"),
    ("npm --prefix website run build", "build_test", "build_package", "script_name_hint"),
    ("uv run --project backend pytest", "build_test", "verify_tests", "known_command"),
    ("python -m compileall -q .", "build_test", "build_package", "known_command"),
    ("git status", "git", "vcs_read", "known_command"),
    ("git push", "git", "vcs_write", "known_command"),
    ("python custom.py", "other", "unknown", "unrecognized"),
])
def test_operation_classification_recognizes_purpose_without_executing(command, category, operation, basis):
    attempt = command_attempts([event(1, command)])[0]
    assert attempt["category"] == category
    assert attempt["classification"]["operation"] == operation
    assert attempt["classification"]["basis"] == basis


@pytest.mark.parametrize("command,operation", [
    ("cd backend && python -m pytest", "verify_tests"),
    ("rg TODO src | head -n 20", "search_content"),
    ("npm test && git push", "unknown"),
])
def test_compound_shape_is_separate_from_inferred_purpose_and_counts_once(command, operation):
    report = analyze_activity([event(1, command)])
    attempt = command_attempts([event(1, command)])[0]
    assert attempt["classification"]["shape"] == "compound"
    assert attempt["classification"]["operation"] == operation
    assert report["attempt_count"] == 1
    assert report["command_shapes"]["compound"] == 1
    assert sum(row["count"] for row in report["operations"]) == 1


def test_operation_breakdown_keeps_results_durations_and_inference_coverage():
    report = analyze_activity([event(1, "npm run test:unit", exit_code=1, duration_ms=30),
        event(2, "pytest", duration_ms=0), event(3, "pytest", tool_response={})])
    row = next(row for row in report["operations"] if row["operation"] == "verify_tests")
    assert row == {"operation": "verify_tests", "count": 3, "success_count": 1, "failed_count": 1,
        "expected_nonzero_count": 0, "unknown_outcome_count": 1, "pending_count": 0, "cancelled_count": 0,
        "duration_sample_count": 2, "reported_duration_ms": 30, "inferred_count": 1}


@pytest.mark.parametrize("command", ["rg absent src", "grep absent sample.txt", "git diff --exit-code", "git diff --quiet"])
def test_normal_nonzero_query_does_not_become_failure_retry_or_risk(command):
    calls = [event(index, command, exit_code=1) for index in range(3)]
    report = analyze_activity(calls)
    assert report["failed_count"] == 3  # The original process outcome remains available.
    assert report["expected_nonzero_count"] == 3
    assert not any(item["code"] == "failed_retry" for item in report["findings"])
    hook = AuditEvent.from_hook({"session_id": "synthetic", "hook_event_name": "PostToolUse",
        "tool_name": "Bash", "tool_input": {"command": command}, "tool_response": {"exit_code": 1}})
    assert not any(item.code == "tool_failure" for item in analyze_event(hook))


@pytest.mark.parametrize("command,phase,code", [
    ("rg absent src", "PostToolUse", 2), ("rg absent src", "PostToolUseFailure", 1),
    ("rg absent src && npm test", "PostToolUse", 1), ("git diff", "PostToolUse", 1),
    ("python -c 'print(1)'", "PostToolUse", 1),
])
def test_expected_nonzero_exceptions_are_narrow(command, phase, code):
    report = analyze_activity([event(index, command, phase=phase, exit_code=code) for index in range(3)])
    assert report["expected_nonzero_count"] == 0
    assert report["findings"][0]["code"] == "failed_retry"


def test_required_exit_zero_contract_still_rejects_query_exit_one():
    from harness.models import Run, TaskContract
    from harness.evaluators import evaluate_verification

    task = TaskContract.create(title="No diff", goal="Require clean diff", target_repositories=["demo"],
        constraints=[], open_questions=[], risk_level="normal", acceptance_criteria=[{
            "criterion_id": "clean", "type": "command_exit_zero", "required": True,
            "description": "No changes", "config": {"command": "git diff --exit-code"}}])
    run = Run.create(task_id=task.task_id, context_snapshot_id="synthetic-snapshot")
    assert evaluate_verification(task, [("e1", "git diff --exit-code", 1)], run)[0].status == "failed"


@pytest.mark.parametrize("command", ["cat sample.txt > copy.txt", "find . -exec custom {} +", "sed -f custom.sed sample.txt",
    'rg "$(cat pattern.txt)" src', 'rg "${PATTERN:?missing}" src',
    "uv run " * 100 + "pytest", 'rg "unterminated'])
def test_opaque_scripts_and_redirection_do_not_claim_a_known_read(command):
    assert command_attempts([event(1, command)])[0]["classification"]["operation"] == "unknown"


def test_git_path_named_like_flag_does_not_enable_expected_exit_one():
    report = analyze_activity([event(1, "git diff -- --exit-code", exit_code=1)])
    assert report["expected_nonzero_count"] == 0


@pytest.mark.parametrize("reverse", [False, True])
def test_query_meaning_uses_paired_start_when_completion_has_no_command(reverse):
    calls = []
    for index in range(3):
        pair = [event(index * 2, "rg absent src", phase="PreToolUse", call=str(index)),
                event(index * 2 + 1, "", call=str(index), exit_code=1)]
        if reverse:
            pair.reverse()
            for offset, item in enumerate(pair):
                item["sequence"] = index * 2 + offset
        calls.extend(pair)
    report = analyze_activity(calls)
    assert report["attempt_count"] == 3
    assert report["expected_nonzero_count"] == 3
    assert report["findings"] == []


def test_no_index_git_diff_does_not_suppress_exit_one_errors():
    report = analyze_activity([event(index, "git diff --no-index --exit-code missing-a missing-b", exit_code=1)
                               for index in range(3)])
    assert report["expected_nonzero_count"] == 0
    assert report["findings"][0]["code"] == "failed_retry"


@pytest.mark.parametrize("command", ["rm artifact.txt 2>/dev/null", "sed -i s/old/new/ sample.txt > edit.log"])
def test_known_mutation_with_redirection_invalidates_previous_verification(command):
    from harness.models import Run, TaskContract
    from harness.evaluators import evaluate_verification

    task = TaskContract.create(title="Verify changes", goal="Require fresh tests", target_repositories=["demo"],
        constraints=[], open_questions=[], risk_level="normal", acceptance_criteria=[{
            "criterion_id": "tests", "type": "command_exit_zero", "required": True,
            "description": "Tests after changes", "config": {"command": "pytest"}}])
    run = Run.create(task_id=task.task_id, context_snapshot_id="synthetic-snapshot")
    result = evaluate_verification(task, [("test", "pytest", 0), ("edit", command, 0)], run)[0]
    assert result.status == "needs_review"
    assert result.reason == "verification_stale"
    classification = command_attempts([event(1, command)])[0]["classification"]
    assert classification["operation"] == "modify_files"
    assert classification["shape"] == "compound"
    assert classification["basis"] == "compound_hint"
