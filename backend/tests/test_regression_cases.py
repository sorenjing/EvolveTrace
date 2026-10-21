import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
FIXTURES = Path(__file__).parent / "fixtures" / "regression-cases.json"


def test_frozen_cases_match_and_report_all_expected_results():
    from harness.regression import replay_suite
    report = replay_suite(json.loads(FIXTURES.read_text(encoding="utf-8")))
    assert report["summary"] == {"total": 10, "matched": 10, "regressions": 0, "errors": 0}
    assert report["claim"] == "evaluator_consistency_only"
    assert all(item["input_digest"] for item in report["cases"])
    assert any(item["outcome_counts"]["needs_review"] for item in report["cases"])


def test_gold_change_is_reported_as_regression_not_silently_rewritten():
    from harness.regression import replay_suite
    suite = json.loads(FIXTURES.read_text(encoding="utf-8"))
    original = copy.deepcopy(suite)
    suite["cases"][0]["expected"][-1]["status"] = "failed"
    report = replay_suite(suite)
    assert report["summary"]["regressions"] == 1
    assert report["cases"][0]["differences"]
    assert original["cases"][0]["expected"][-1]["status"] == "passed"
    assert suite["cases"][0]["expected"][-1]["status"] == "failed"


def test_malformed_case_stays_in_denominator_and_other_cases_continue():
    from harness.regression import replay_suite
    suite = json.loads(FIXTURES.read_text(encoding="utf-8"))
    suite["cases"][1]["events"][0]["details"] = "invalid"
    report = replay_suite(suite)
    assert report["summary"] == {"total": 10, "matched": 9, "regressions": 0, "errors": 1}
    assert report["cases"][1]["reason"] == "invalid_case"


@pytest.mark.parametrize("field,value", [("title", None), ("title", 42), ("goal", []),
                                        ("acceptance_criteria", None), ("constraints", "text")])
def test_malformed_task_stays_in_report(field, value):
    from harness.regression import replay_suite
    suite = json.loads(FIXTURES.read_text(encoding="utf-8"))
    suite["cases"][0]["task"][field] = value
    report = replay_suite(suite)
    assert report["summary"] == {"total": 10, "matched": 9, "regressions": 0, "errors": 1}
    assert report["cases"][0]["reason"] == "invalid_case"


@pytest.mark.parametrize("field,value", [("status", "accepted"), ("severity", "critical")])
def test_invalid_gold_vocabulary_is_an_input_error(field, value):
    from harness.regression import replay_suite
    suite = json.loads(FIXTURES.read_text(encoding="utf-8"))
    suite["cases"][0]["expected"][0][field] = value
    report = replay_suite(suite)
    assert report["summary"]["errors"] == 1
    assert report["cases"][0]["reason"] == "invalid_case"


@pytest.mark.parametrize("path", ["../escape", "C:/private", "/private"])
def test_nonportable_directories_are_rejected(path):
    from harness.regression import replay_suite
    suite = json.loads(FIXTURES.read_text(encoding="utf-8"))
    suite["cases"][0]["run"]["cwd"] = path
    assert replay_suite(suite)["cases"][0]["status"] == "error"


def test_cli_only_scores_data_and_never_executes_recorded_commands(tmp_path):
    suite = json.loads(FIXTURES.read_text(encoding="utf-8"))
    sentinel = tmp_path / "must-not-exist"
    command = f'python -c "open({str(sentinel)!r}, \'w\').write(\'unexpected\')"'
    case = suite["cases"][0]
    case["task"]["acceptance_criteria"][0]["config"]["command"] = command
    for event in case["events"]:
        if event.get("tool_name") == "Bash":
            event["details"]["tool_input"]["command"] = command
    source = tmp_path / "suite.json"
    source.write_text(json.dumps(suite), encoding="utf-8")
    report_path = tmp_path / "report.json"
    process = subprocess.run([sys.executable, str(ROOT / "scripts/replay_regressions.py"),
                              str(source), "--output", str(report_path)], capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert json.loads(report_path.read_text())["summary"]["matched"] == 10
    assert not sentinel.exists()
    suite["cases"][0]["expected"][-1]["status"] = "failed"
    source.write_text(json.dumps(suite), encoding="utf-8")
    failed = subprocess.run([sys.executable, str(ROOT / "scripts/replay_regressions.py"), str(source)], capture_output=True, text=True)
    assert failed.returncode == 1
