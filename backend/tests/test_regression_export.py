import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

import api.routes as routes
from harness.regression import replay_suite
from main import app
from test_review_workflow import workflow, complete


ROOT = Path(__file__).resolve().parents[2]


def export_fixture(tmp_path):
    harness, task, audit = workflow(tmp_path)
    run, _ = complete(harness, task, audit, "synthetic-export", 1)
    return harness, task, audit, run


def draft_for(harness, task, audit, run):
    return harness.export_regression_draft(task["task_id"], run["run_id"], audit.get_session("synthetic-export"),
                                           workspace_root="/synthetic", case_id="failed-verification")


def test_export_is_portable_minimal_and_does_not_invent_gold(tmp_path):
    harness, task, audit, run = export_fixture(tmp_path)
    session = audit.get_session("synthetic-export")
    session["events"][0]["details"].update(prompt="PRIVATE PROMPT", transcript_path="/private/transcript.jsonl")
    session["events"][0]["details"]["tool_response"]["output"] = "PRIVATE SOURCE"
    draft = harness.export_regression_draft(task["task_id"], run["run_id"], session,
        workspace_root="/synthetic", case_id="failed-verification")
    assert draft["schema_version"] == "regression-draft/v1"
    assert draft["case"]["expected"] == []
    assert draft["review"]["status"] == "pending"
    assert draft["case"]["run"] == {"cwd": "sample-app"}
    rendered = json.dumps(draft)
    for private in ("PRIVATE PROMPT", "PRIVATE SOURCE", "/synthetic", "/private", "synthetic-export", "notes", "facts"):
        assert private not in rendered
    assert draft["source"]["run_id"] == run["run_id"]
    assert draft["source"]["event_count"] == 2
    assert len(draft["input_digest"]) == 64
    assert len(draft["case"]["events"]) == 2
    assert draft["case"]["events"][0]["details"]["tool_response"] == {"exit_code": 1}
    assert harness.repository.get_run(run["run_id"]).status == "completed"


def reviewed(draft):
    draft = copy.deepcopy(draft)
    draft["case"]["expected"] = [
        {"criterion_id": "context-freshness", "evaluator_id": "context-freshness", "evaluator_version": "1",
         "status": "passed", "severity": "blocking", "reason": "context_declared_current"},
        {"criterion_id": "tests", "evaluator_id": "verification", "evaluator_version": "2",
         "status": "failed", "severity": "blocking", "reason": "verification_failed"},
    ]
    draft["review"] = {"status": "confirmed", "reviewer": "Synthetic reviewer", "basis": "Checked the literal exit 1 evidence"}
    return draft


def test_only_reviewed_unchanged_input_can_be_frozen_and_replayed(tmp_path):
    from harness.regression_export import freeze_draft
    harness, task, audit, run = export_fixture(tmp_path)
    draft = draft_for(harness, task, audit, run)
    with pytest.raises(ValueError, match="review"):
        freeze_draft(draft)
    approved = reviewed(draft)
    suite = freeze_draft(approved)
    assert replay_suite(suite)["summary"] == {"total": 1, "matched": 1, "regressions": 0, "errors": 0}
    approved["case"]["events"][0]["details"]["tool_response"]["exit_code"] = 0
    with pytest.raises(ValueError, match="digest"):
        freeze_draft(approved)


def test_freezing_does_not_require_agreement_with_current_evaluator(tmp_path):
    from harness.regression_export import freeze_draft
    harness, task, audit, run = export_fixture(tmp_path)
    draft = reviewed(draft_for(harness, task, audit, run))
    draft["case"]["expected"][1]["status"] = "needs_review"
    draft["case"]["expected"][1]["reason"] = "outcome_unknown"
    assert replay_suite(freeze_draft(draft))["summary"]["regressions"] == 1


@pytest.mark.parametrize("change", ["running", "wrong-session", "missing-session", "outside-workspace", "too-many-events", "absolute-command"])
def test_export_refuses_incomplete_or_nonportable_data_without_silent_truncation(tmp_path, change):
    harness, task, audit, run = export_fixture(tmp_path)
    session = audit.get_session("synthetic-export")
    root = "/synthetic"
    if change == "running":
        harness.repository.set_run_status(run["run_id"], "running")
    elif change == "wrong-session":
        session["session_id"] = "unrelated"
    elif change == "missing-session":
        session = None
    elif change == "outside-workspace":
        root = "/different"
    elif change == "too-many-events":
        session["events"] = session["events"] * 501
    else:
        session["events"][0]["details"]["tool_input"]["command"] = "python /private/check.py"
    with pytest.raises(ValueError):
        harness.export_regression_draft(task["task_id"], run["run_id"], session, workspace_root=root, case_id="synthetic")


def test_export_retains_resolved_conflicts_and_pairing(tmp_path):
    harness, task, audit, run = export_fixture(tmp_path)
    session = audit.get_session("synthetic-export")
    session["events"][0]["details"]["tool_use_id"] = "private-call-id"
    session["events"][0]["_execution_result"] = {"outcome": "success", "exit_code": 0, "duration_ms": None,
        "started_at": None, "completed_at": None, "conflict": True}
    from harness.models import Run
    from harness.regression_export import build_draft, freeze_draft
    draft = build_draft(harness.repository.get_task(task["task_id"]), harness.repository.get_context_snapshot(task["context_snapshot_id"]),
        Run.create(task_id=task["task_id"], context_snapshot_id=task["context_snapshot_id"], run_id=run["run_id"], cwd="/synthetic/sample-app"),
        session["events"], workspace_root="/synthetic", case_id="conflict")
    assert "private-call-id" not in json.dumps(draft)
    assert draft["case"]["events"][0]["_execution_result"]["conflict"] is True
    approved = reviewed(draft)
    approved["case"]["expected"][1].update(status="needs_review", reason="outcome_unknown")
    assert replay_suite(freeze_draft(approved))["summary"]["matched"] == 1


def test_export_api_is_loopback_only_and_checks_run_ownership(tmp_path, monkeypatch):
    harness, task, audit, run = export_fixture(tmp_path)
    monkeypatch.setattr(routes, "harness_service", harness)
    monkeypatch.setattr(routes, "audit_service", audit)
    path = f"/api/harness/tasks/{task['task_id']}/runs/{run['run_id']}/regression-draft"
    payload = {"workspace_root": "/synthetic", "case_id": "api-case"}
    assert TestClient(app, client=("10.0.0.1", 1234)).post(path, json=payload).status_code == 403
    client = TestClient(app, client=("127.0.0.1", 1234))
    response = client.post(path, json=payload)
    assert response.status_code == 200
    assert response.json()["case"]["expected"] == []
    assert client.post(path.replace(task["task_id"], "unrelated"), json=payload).status_code == 422


def test_freeze_cli_keeps_gold_and_never_overwrites_existing_output(tmp_path):
    harness, task, audit, run = export_fixture(tmp_path)
    draft = reviewed(draft_for(harness, task, audit, run))
    source, output = tmp_path / "draft.json", tmp_path / "suite.json"
    source.write_text(json.dumps(draft), encoding="utf-8")
    command = [sys.executable, str(ROOT / "scripts/regression_cases.py"), "freeze", str(source), "--output", str(output)]
    first = subprocess.run(command, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    assert replay_suite(json.loads(output.read_text()))["summary"]["matched"] == 1
    output.write_text("keep existing", encoding="utf-8")
    again = subprocess.run(command, capture_output=True, text=True)
    assert again.returncode != 0
    assert output.read_text() == "keep existing"


def test_projection_refuses_to_hide_directory_uncertainty(tmp_path):
    from harness.models import Run
    from harness.regression_export import build_draft
    harness, task, audit, run = export_fixture(tmp_path)
    source = audit.get_session("synthetic-export")["events"]
    source[0]["cwd"] = ""
    with pytest.raises(ValueError):
        build_draft(harness.repository.get_task(task["task_id"]), harness.repository.get_context_snapshot(task["context_snapshot_id"]),
            Run.create(task_id=task["task_id"], context_snapshot_id=task["context_snapshot_id"], cwd="/synthetic/sample-app"),
            source, workspace_root="/synthetic", case_id="unknown-directory")


def test_oversized_projection_is_rejected_before_scoring(tmp_path, monkeypatch):
    from harness import regression_export
    harness, task, audit, run = export_fixture(tmp_path)
    source = audit.get_session("synthetic-export")["events"]
    source[0]["details"]["tool_input"]["command"] = "x" * (4 * 1024 * 1024)
    def unexpected_score(*args):
        pytest.fail("oversized export must not reach scoring")
    monkeypatch.setattr(regression_export, "evaluate_evidence", unexpected_score)
    with pytest.raises(ValueError, match="4 MiB"):
        regression_export.build_draft(harness.repository.get_task(task["task_id"]),
            harness.repository.get_context_snapshot(task["context_snapshot_id"]), harness.repository.get_run(run["run_id"]),
            source, workspace_root="/synthetic", case_id="oversized")


@pytest.mark.parametrize("location,field", [("details", "status"), ("details", "exit_code"),
    ("details", "duration_ms"), ("tool_response", "status"), ("tool_response", "exit_code"),
    ("tool_input", "command"), ("repository_state", "head_commit"), ("event", "timestamp")])
def test_arbitrary_nested_content_in_scalar_fields_is_rejected(tmp_path, location, field):
    harness, task, audit, run = export_fixture(tmp_path)
    session = audit.get_session("synthetic-export")
    event = session["events"][0]
    target = event if location == "event" else event["details"] if location == "details" else event["details"].setdefault(location, {})
    target[field] = {"prompt": "SYNTHETIC BODY THAT SHOULD BE OMITTED"}
    with pytest.raises(ValueError, match="typed"):
        harness.export_regression_draft(task["task_id"], run["run_id"], session,
            workspace_root="/synthetic", case_id="malformed")


def test_near_limit_cli_output_remains_readable_by_freeze_and_replay(tmp_path):
    from harness.regression import MAX_SUITE_BYTES, _digest
    harness, task, audit, run = export_fixture(tmp_path)
    draft = reviewed(draft_for(harness, task, audit, run))
    sample = copy.deepcopy(draft["case"]["events"][0])
    sample["details"]["tool_input"]["command"] = "echo " + "a" * 3800
    draft["case"]["events"] = [{**copy.deepcopy(sample), "event_id": f"event-{index}"} for index in range(1000)]
    draft["input_digest"] = _digest({key: value for key, value in draft["case"].items() if key != "expected"})
    source, output = tmp_path / "near-limit.json", tmp_path / "frozen-limit.json"
    source.write_text(json.dumps(draft, separators=(",", ":")), encoding="utf-8")
    assert source.stat().st_size < MAX_SUITE_BYTES
    command = [sys.executable, str(ROOT / "scripts/regression_cases.py"), "freeze", str(source), "--output", str(output)]
    process = subprocess.run(command, capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    assert output.stat().st_size <= MAX_SUITE_BYTES
    report = replay_suite(json.loads(output.read_text()))
    assert report["summary"]["total"] == 1
    assert report["summary"]["errors"] == 0


def test_export_cli_reads_only_loopback_and_refuses_redirects(tmp_path):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading
    harness, task, audit, run = export_fixture(tmp_path)
    draft = draft_for(harness, task, audit, run)
    class Handler(BaseHTTPRequestHandler):
        redirect = False

        def do_POST(self):
            if self.path != f"/api/harness/tasks/{task['task_id']}/runs/{run['run_id']}/regression-draft":
                self.send_error(404)
                return
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if request != {"workspace_root": "/synthetic", "case_id": "failed-verification"}:
                self.send_error(400)
                return
            if self.redirect:
                self.send_response(302)
                self.send_header("Location", "/redirected")
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(draft).encode())

        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(draft).encode())

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        command = [sys.executable, str(ROOT / "scripts/regression_cases.py"), "export", "--task-id", task["task_id"],
            "--run-id", run["run_id"], "--workspace-root", "/synthetic", "--case-id", "failed-verification",
            "--url", f"http://127.0.0.1:{server.server_port}", "--output", str(tmp_path / "exported.json")]
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert json.loads((tmp_path / "exported.json").read_text())["case"]["expected"] == []
        Handler.redirect = True
        command[-1] = str(tmp_path / "redirected.json")
        assert subprocess.run(command, capture_output=True, text=True).returncode == 2
        assert not (tmp_path / "redirected.json").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
