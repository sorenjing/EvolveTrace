import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit.models import AuditEvent
from audit.repository import AuditRepository


def make_event(session_id: str, sequence: int, event_type: str = "PreToolUse") -> AuditEvent:
    return AuditEvent.from_hook(
        {
            "event_id": f"evt-{session_id}-{sequence}",
            "session_id": session_id,
            "turn_id": "turn-1",
            "sequence": sequence,
            "hook_event_name": event_type,
            "timestamp": f"2026-08-06T10:00:0{sequence}Z",
            "cwd": "D:/repo",
            "tool_name": "Bash",
            "tool_input": {"command": "git status"},
        }
    )


def test_repository_orders_events_and_aggregates_sessions(tmp_path):
    repository = AuditRepository(tmp_path / "audit.db")
    repository.add_event(make_event("session-1", 2))
    repository.add_event(make_event("session-1", 1))
    repository.add_event(make_event("session-2", 1, "Stop"))

    sessions = repository.list_sessions()
    session = repository.get_session("session-1")

    assert {item["session_id"] for item in sessions} == {"session-1", "session-2"}
    assert session["event_count"] == 2
    assert [item["sequence"] for item in session["events"]] == [1, 2]
    assert session["tool_call_count"] == 2


def test_repository_deletes_one_session_without_affecting_another(tmp_path):
    repository = AuditRepository(tmp_path / "audit.db")
    repository.add_event(make_event("session-1", 1))
    repository.add_event(make_event("session-2", 1))

    assert repository.delete_session("session-1") is True
    assert repository.get_session("session-1") is None
    assert repository.get_session("session-2") is not None
    assert repository.delete_session("missing") is False


def test_repository_configures_wal_and_busy_timeout(tmp_path):
    repository = AuditRepository(tmp_path / "audit.db")

    with repository._connect() as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] >= 1000
