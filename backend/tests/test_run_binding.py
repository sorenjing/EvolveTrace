import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit.repository import AuditRepository
from services.audit_service import AuditService
from services.harness_service import HarnessService
from harness.repository import HarnessRepository


def bundle():
    return {"schema_version":"context-bundle/v1","project":"sample-app","generated_at":"2026-09-09T00:00:00+00:00","freshness":"current","observed_scope":["sample-app"],"repositories":[{"name":"sample-app","relative_path":"sample-app"}],"context":{"automatic":"facts","manual":"notes"}}


def payload(session_id, cwd):
    return {"event_id":f"event-{session_id}","session_id":session_id,"hook_event_name":"PostToolUse","cwd":cwd,"tool_name":"Bash"}


def configured(tmp_path):
    harness = HarnessService(HarnessRepository(tmp_path / "harness.db"))
    snapshot = harness.import_context_snapshot(bundle())
    task = harness.create_task({"title":"Bind evidence","goal":"Attach audit sessions","target_repositories":["sample-app"],"constraints":[],"acceptance_criteria":[],"open_questions":[],"risk_level":"normal","status":"ready","context_snapshot_id":snapshot["snapshot_id"]})
    audit = AuditService(AuditRepository(tmp_path / "audit.db"), run_resolver=harness.resolve_or_create_run)
    return harness, task, audit


def configured_with_receipt(tmp_path):
    harness, task, audit = configured(tmp_path)
    harness.ingest_context_receipt({
        "schema": "context-receipt/v1",
        "receipt_id": "receipt-1",
        "task_id": task["task_id"],
        "context_snapshot_id": task["context_snapshot_id"],
        "attempt_id": "unassigned",
        "bundle_id": "ctx_1",
        "platform": "codex",
        "adapter": "evolvetrace-http",
        "status": "delivered",
        "delivered_source_ids": ["context:sample-app:rendered"],
        "loaded_skill_ids": [],
    })
    return harness, task, audit


def test_first_event_creates_run_for_active_repository(tmp_path):
    harness, task, audit = configured(tmp_path)
    harness.activate_task(task["task_id"], "sample-app")
    result = audit.ingest(payload("s1", r"C:\workspace\sample-app"))
    assert result["run"]["task_id"] == task["task_id"]


def test_unmatched_session_remains_unbound(tmp_path):
    harness, _, audit = configured(tmp_path)
    result = audit.ingest(payload("s2", "other-app"))
    assert result["run"] is None
    assert harness.list_unbound_runs()[0]["session_id"] == "s2"


def test_default_routes_wire_audit_events_to_the_harness():
    import api.routes as routes
    assert routes.audit_service.run_resolver == routes.harness_service.resolve_or_create_run


def test_most_specific_active_repository_wins(tmp_path):
    harness, task, audit = configured(tmp_path)
    sibling = harness.create_task({"title":"Nested task","goal":"Use the nested repository","target_repositories":["workspace/sample-app"],"constraints":[],"acceptance_criteria":[],"open_questions":[],"risk_level":"normal","status":"ready","context_snapshot_id":task["context_snapshot_id"]})
    harness.activate_task(task["task_id"], "sample-app")
    harness.activate_task(sibling["task_id"], "workspace/sample-app")
    assert audit.ingest(payload("specific", r"C:\root\workspace\sample-app"))["run"]["task_id"] == sibling["task_id"]


def test_first_bound_hook_acknowledges_delivered_receipt(tmp_path):
    harness, task, audit = configured_with_receipt(tmp_path)
    harness.activate_task(task["task_id"], "sample-app")

    result = audit.ingest(payload("receipt-session", r"C:\workspace\sample-app"))

    receipt = harness.list_context_receipts(task["task_id"])[0]
    assert receipt["status"] == "acknowledged"
    assert receipt["attempt_id"] == result["run"]["run_id"]


def test_stop_hook_completes_bound_run(tmp_path):
    harness, task, audit = configured(tmp_path)
    harness.activate_task(task["task_id"], "sample-app")
    audit.ingest(payload("done", "sample-app"))
    stop = payload("done", "sample-app")
    stop["event_id"] = "event-stop"
    stop["hook_event_name"] = "Stop"
    result = audit.ingest(stop)
    assert result["run"]["status"] == "completed"
