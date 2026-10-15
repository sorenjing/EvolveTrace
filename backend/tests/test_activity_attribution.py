import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit.repository import AuditRepository
from services.activity_service import ActivityService
from services.audit_service import AuditService


@pytest.fixture
def setup(tmp_path, monkeypatch):
    home = tmp_path / "codex"
    (home / "sessions").mkdir(parents=True)
    monkeypatch.setenv("CODEX_HOME", str(home))
    audit = AuditService(AuditRepository(tmp_path / "audit.db"))
    activity = ActivityService(audit.repository)
    workspace = tmp_path / "workspace"
    activity.repository.register({"schema_version": "workspace-index/v1", "workspace_root": str(workspace),
                                 "projects": [{"name": "demo", "relative_path": "demo"},
                                              {"name": "other", "relative_path": "other"}]})
    return audit, activity, workspace, home


def completed(workspace, call="call-1", *, thread="s-1", cwd=None):
    return {"type": "event_msg", "payload": {"type": "item_completed", "thread_id": thread,
            "item": {"type": "CommandExecution", "id": call, "cwd": cwd or (workspace / "demo").as_uri(),
                     "aggregated_output": "synthetic output must not enter attribution"}}}


def transcript(home, records, *, session="s-1", outside=False):
    path = home / ("outside.jsonl" if outside else "sessions/rollout-synthetic.jsonl")
    header = {"type": "session_meta", "payload": {"id": session}}
    path.write_text("\n".join(json.dumps(value) for value in [header, *records]) + "\n", encoding="utf-8")
    return str(path)


def ingest(audit, workspace, path=None, *, call="call-1", phase="PostToolUse", workdir=None):
    return audit.ingest({"event_id": f"{call}-{phase}", "session_id": "s-1", "hook_event_name": phase,
                         "cwd": str(workspace), "tool_name": "Bash", "tool_use_id": call,
                         "tool_input": {"command": "git status", **({"workdir": workdir} if workdir else {})},
                         **({"transcript_path": path} if path else {})})["event"]["event_id"]


def by_name(activity):
    return {project["name"]: project for project in activity.report()["projects"]}


def test_exact_completed_call_backfills_both_phases_and_preserves_raw_evidence(setup):
    audit, activity, workspace, home = setup
    path = transcript(home, [completed(workspace)])
    refs = [ingest(audit, workspace, path, phase=phase) for phase in ("PreToolUse", "PostToolUse")]
    report = activity.report()
    assert by_name(activity)["demo"]["activity"]["attempt_count"] == 1
    assert report["unattributed_event_count"] == 0
    assert report["attribution_sources"]["execution_record"] == 2
    assert all(event["cwd"] == str(workspace) for event in audit.get_session("s-1")["events"])
    assert "synthetic output" not in str(report)
    assert str(home) not in str(report)
    project = by_name(activity)["demo"]
    note = activity.remember({"project_id": project["project_id"], "session_id": "s-1", "evidence_refs": refs,
                              "note": "Synthetic reviewed observation", "confirmed": True})
    assert note["evidence_refs"] == refs
    with pytest.raises(ValueError, match="does not belong"):
        activity.remember({"project_id": by_name(activity)["other"]["project_id"], "session_id": "s-1",
                           "evidence_refs": refs, "note": "Wrong project", "confirmed": True})


def test_explicit_tool_workdir_takes_precedence_over_session_directory(setup):
    audit, activity, workspace, _ = setup
    ingest(audit, workspace, workdir=str(workspace / "other"))
    assert by_name(activity)["other"]["activity"]["attempt_count"] == 1
    assert activity.report()["attribution_sources"]["tool_workdir"] == 1


@pytest.mark.parametrize("mismatch", ["session", "thread", "call", "outside", "remote_uri"])
def test_unverified_execution_metadata_stays_unattributed(setup, mismatch):
    audit, activity, workspace, home = setup
    record = completed(workspace, call="different" if mismatch == "call" else "call-1",
                       thread="different" if mismatch == "thread" else "s-1",
                       cwd="file://remote-host/share/demo" if mismatch == "remote_uri" else None)
    path = transcript(home, [record], session="different" if mismatch == "session" else "s-1", outside=mismatch == "outside")
    ingest(audit, workspace, path)
    assert activity.report()["unattributed_event_count"] == 1
    assert activity.report()["attribution_sources"]["execution_record"] == 0


def test_bounded_tail_does_not_scan_old_completed_records(setup):
    audit, activity, workspace, home = setup
    path = transcript(home, [completed(workspace)])
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "response_item", "payload": {"type": "message", "content": "x" * (1024 * 1024 + 100)}}))
    ingest(audit, workspace, path)
    report = activity.report()
    assert report["unattributed_event_count"] == 1
    assert report["execution_metadata_scan"]["limited"] is True


def test_verified_directory_receipts_survive_log_growth_restart_and_delete_with_event(setup):
    audit, activity, workspace, home = setup
    path = transcript(home, [completed(workspace)])
    ingest(audit, workspace, path)
    assert by_name(activity)["demo"]["activity"]["attempt_count"] == 1
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"type": "response_item", "payload": {"type": "message", "content": "x" * (1024 * 1024 + 100)}}))
    restarted = ActivityService(audit.repository)
    assert by_name(restarted)["demo"]["activity"]["attempt_count"] == 1
    assert restarted.report()["execution_metadata_scan"]["files_read"] == 0
    assert audit.delete_session("s-1") is True
    with restarted.repository._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM activity_execution_directories").fetchone()[0] == 0


def test_one_call_never_assigns_other_calls_in_the_same_session(setup):
    audit, activity, workspace, home = setup
    path = transcript(home, [completed(workspace)])
    ingest(audit, workspace, path)
    ingest(audit, workspace, path, call="call-2")
    assert by_name(activity)["demo"]["activity"]["attempt_count"] == 1
    assert activity.report()["unattributed_event_count"] == 1


def test_malformed_file_uri_does_not_break_reports(setup):
    audit, activity, workspace, home = setup
    path = transcript(home, [completed(workspace, cwd="file://[broken/demo")])
    ingest(audit, workspace, path)
    assert activity.report()["unattributed_event_count"] == 1


def test_conflicting_completed_directories_are_not_used(setup):
    audit, activity, workspace, home = setup
    path = transcript(home, [completed(workspace), completed(workspace, cwd=(workspace / "other").as_uri())])
    ingest(audit, workspace, path)
    assert activity.report()["unattributed_event_count"] == 1


def test_metadata_file_count_is_bounded(setup):
    audit, activity, workspace, home = setup
    for index in range(5):
        path = Path(transcript(home, [completed(workspace, call=f"call-{index}")]))
        unique = path.with_name(f"rollout-{index}.jsonl")
        path.rename(unique)
        ingest(audit, workspace, str(unique), call=f"call-{index}")
    report = activity.report()
    assert report["execution_metadata_scan"]["files_read"] == 4
    assert report["execution_metadata_scan"]["limited"] is True
    assert report["unattributed_event_count"] == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows extended-length path contract")
def test_windows_extended_path_matches_normal_sessions_root(setup):
    audit, activity, workspace, home = setup
    path = transcript(home, [completed(workspace)])
    ingest(audit, workspace, "\\\\?\\" + path)
    assert by_name(activity)["demo"]["activity"]["attempt_count"] == 1
