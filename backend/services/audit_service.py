import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import AsyncIterator

from audit.models import AuditEvent
from audit.repository import AuditRepository
from audit.risk import analyze_event


def _default_database_path() -> Path:
    configured_path = os.getenv("EVOLVETRACE_DB_PATH")
    if configured_path:
        return Path(configured_path)
    return Path(tempfile.gettempdir()) / "evolvetrace" / "audit.db"


class AuditService:
    def __init__(
        self,
        repository: AuditRepository | None = None,
        queue_size: int = 100,
        heartbeat_interval: float = 15.0,
    ):
        self.repository = repository or AuditRepository(_default_database_path())
        self.queue_size = queue_size
        self.heartbeat_interval = heartbeat_interval
        self._subscribers: list[tuple[str | None, asyncio.Queue]] = []

    def ingest(self, payload: dict) -> dict:
        prepared_payload = dict(payload)
        if "sequence" not in prepared_payload or prepared_payload["sequence"] is None:
            preview = AuditEvent.from_hook({**prepared_payload, "sequence": 0})
            prepared_payload["sequence"] = (
                self.repository.event_sequence(preview.event_id)
                or self.repository.next_sequence(preview.session_id)
            )
        event = AuditEvent.from_hook(prepared_payload)
        findings = analyze_event(event)
        persisted = self.repository.add_event(event, findings)
        result = {
            "event": event.to_dict(),
            "risk_findings": [finding.to_dict() for finding in findings],
            "persisted": persisted,
        }
        if persisted:
            self._publish(event.session_id, result)
        return result

    def list_sessions(self) -> list[dict]:
        return self.repository.list_sessions()

    def get_session(self, session_id: str) -> dict | None:
        return self.repository.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        return self.repository.delete_session(session_id)

    def _publish(self, session_id: str, result: dict) -> None:
        for subscriber_session_id, queue in list(self._subscribers):
            if subscriber_session_id is None or subscriber_session_id == session_id:
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(result)

    async def stream(self, session_id: str | None = None) -> AsyncIterator[str]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.queue_size)
        subscription = (session_id, queue)
        self._subscribers.append(subscription)
        try:
            while True:
                try:
                    result = await asyncio.wait_for(
                        queue.get(), timeout=self.heartbeat_interval
                    )
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue
                yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
        finally:
            if subscription in self._subscribers:
                self._subscribers.remove(subscription)
