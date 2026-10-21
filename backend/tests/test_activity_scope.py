import pytest

from test_activity import event
from audit.repository import AuditRepository
from services.audit_service import AuditService
from services.activity_service import ActivityService


@pytest.fixture
def setup(tmp_path):
    audit = AuditService(AuditRepository(tmp_path / "audit.db"))
    return ActivityService(audit.repository), audit, tmp_path


def register(service, root):
    return service.repository.register({
        "schema_version": "workspace-index/v1", "workspace_root": str(root),
        "projects": [{"name": "demo", "relative_path": "projects/demo"},
                     {"name": "nested", "relative_path": "projects/demo/nested"}],
    })


def ingest(audit, root, session="s-1", nested=False):
    for index in range(5):
        payload = event(index)
        payload["hook_event_name"] = payload.pop("event_type")
        payload.update(payload.pop("details"))
        payload.update(session_id=session, event_id=f"{session}-{nested}-{index}",
                       cwd=str(root / "projects/demo" / ("nested/sub" if nested else "src")))
        audit.ingest(payload)


def test_session_report_filters_statistics_findings_and_navigation(setup):
    service, audit, root = setup
    index = register(service, root)
    ingest(audit, root, "first")
    ingest(audit, root, "second")
    report = service.report(session_id="second")
    assert report["scope"]["session_id"] == "second"
    assert report["observed_event_count"] == 5
    assert report["overall_activity"]["attempt_count"] == 5
    project = next(item for item in report["projects"] if item["project_id"] == index["projects"][0]["project_id"])
    assert project["session_count"] == 1
    assert [item["session_id"] for item in project["sessions"]] == ["second"]
    assert set(project["event_ids"]) == {f"second-False-{index}" for index in range(5)}
    assert all(item["session_id"] == "second" for item in project["activity"]["findings"])


def test_project_navigation_uses_event_attribution_and_has_no_absolute_paths(setup):
    service, audit, root = setup
    register(service, root)
    ingest(audit, root, "shared")
    ingest(audit, root, "shared", nested=True)
    report = service.report()
    assert {item["name"] for item in report["projects"] if item["sessions"]} == {"demo", "nested"}
    for project in report["projects"]:
        assert project["sessions"][0]["session_id"] == "shared"
        assert "cwd" not in project["sessions"][0]
    assert str(root) not in str(report)
    scoped = service.report(session_id="shared")
    demo = next(item for item in scoped["projects"] if item["name"] == "demo")
    nested = next(item for item in scoped["projects"] if item["name"] == "nested")
    assert set(demo["event_ids"]).isdisjoint(nested["event_ids"])
    assert len(demo["event_ids"]) == len(nested["event_ids"]) == 5


def test_empty_session_has_explicit_scope_and_policy_not_global_fallback(setup):
    service, audit, root = setup
    register(service, root)
    ingest(audit, root)
    report = service.report(session_id="absent")
    assert report["scope"]["session_id"] == "absent"
    assert report["overall_activity"]["attempt_count"] == 0
    assert all(item["sessions"] == [] for item in report["projects"])
    assert report["rule_policy"] == {
        "version": "activity/v1", "window_seconds": 600,
        "repeated_operation_min": 5, "failed_retry_min": 3,
        "window_anchor": "latest_observed_call_per_session", "calibration": "heuristic",
    }


def test_session_filter_preserves_global_event_limit_boundary(setup):
    service, audit, root = setup
    register(service, root)
    ingest(audit, root, "older")
    ingest(audit, root, "newer")
    report = service.report(session_id="older", limit=2)
    assert report["truncated"] is True
    assert report["observed_event_count"] == 0
    assert report["event_limit"] == 2


def test_unattributed_session_event_ids_share_the_bounded_statistics_window(setup):
    service, audit, root = setup
    ingest(audit, root, "older")
    ingest(audit, root, "newer")
    partial = service.report(session_id="older", limit=7)
    assert partial["projects"] == []
    assert partial["unattributed_event_count"] == partial["observed_event_count"] == 2
    assert set(partial["event_ids"]) == {"older-False-3", "older-False-4"}
    assert service.report(session_id="older", limit=2)["event_ids"] == []
    assert "event_ids" not in service.report(limit=2)
