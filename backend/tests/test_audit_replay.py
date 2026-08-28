import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit.repository import AuditRepository
from services.audit_service import AuditService


FIXTURE = Path(__file__).parent / "fixtures" / "codex_hook_session.json"


def test_replay_restores_one_sanitized_copy_of_each_hook_event(tmp_path):
    events = json.loads(FIXTURE.read_text(encoding="utf-8"))
    service = AuditService(AuditRepository(tmp_path / "audit.db"))

    for payload in events:
        assert service.ingest(payload)["persisted"] is True
        assert service.ingest(payload)["persisted"] is False

    session = service.get_session("fixture-session")
    serialized = json.dumps(session, ensure_ascii=False)

    assert session is not None
    assert session["event_count"] == len(events)
    assert session["risk_count"] >= 1
    assert "fixture-token" not in serialized
    assert "[REDACTED]" in serialized
