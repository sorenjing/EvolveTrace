import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit.repository import AuditRepository
from services.audit_service import AuditService


def hook_payload(event_type="PostToolUse"):
    return {
        "session_id": "session-service",
        "turn_id": "turn-1",
        "hook_event_name": event_type,
        "tool_name": "Bash",
        "tool_use_id": "tool-1",
        "tool_input": {"command": "git status"},
    }


def test_service_assigns_sequences_and_deduplicates_tool_events(tmp_path):
    service = AuditService(AuditRepository(tmp_path / "audit.db"))
    queue = asyncio.Queue()
    service._subscribers.append((None, queue))

    first = service.ingest(hook_payload())
    duplicate = service.ingest(hook_payload())
    different_event = service.ingest(hook_payload("PostToolUseFailure"))

    assert first["persisted"] is True
    assert first["event"]["sequence"] == 1
    assert duplicate["persisted"] is False
    assert different_event["persisted"] is True
    assert different_event["event"]["sequence"] == 2
    assert queue.qsize() == 2


def test_sse_stream_has_bounded_queue_and_heartbeat(tmp_path):
    async def run():
        service = AuditService(
            AuditRepository(tmp_path / "audit.db"),
            queue_size=2,
            heartbeat_interval=0.01,
        )
        stream = service.stream()
        assert await stream.__anext__() == ": heartbeat\n\n"
        assert service._subscribers[0][1].maxsize == 2
        await stream.aclose()

    asyncio.run(run())
