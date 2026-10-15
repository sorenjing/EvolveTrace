import asyncio
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from audit.models import AuditEvent
from audit.repository import AuditRepository
from audit.risk import analyze_event


CAPTURE_PHASES = {
    "SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse",
    "PostToolUse", "PostToolUseFailure", "PermissionRequest", "Stop",
    "SubagentStart", "SubagentStop", "PreCompact", "PostCompact",
}


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
        run_resolver=None,
    ):
        self.repository = repository or AuditRepository(_default_database_path())
        self.queue_size = queue_size
        self.heartbeat_interval = heartbeat_interval
        self.run_resolver = run_resolver
        self._subscribers: list[tuple[str | None, asyncio.Queue]] = []
        self._capture_lock = threading.Lock()
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._last_received_at: str | None = None
        self._received_count = 0
        self._persisted_count = 0
        self._observed_phases: set[str] = set()

    def capture_status(self) -> dict:
        with self._capture_lock:
            return {"started_at": self._started_at, "process_id": os.getpid(),
                    "last_received_at": self._last_received_at,
                    "received_event_count": self._received_count,
                    "persisted_event_count": self._persisted_count,
                    "observed_phases": sorted(self._observed_phases)}

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
        # Receipt time is local server time; old/replayed event timestamps do
        # not imply that the current collector is silent or disconnected.
        with self._capture_lock:
            self._last_received_at = datetime.now(timezone.utc).isoformat()
            self._received_count += 1
            self._persisted_count += int(persisted)
            if event.event_type in CAPTURE_PHASES:
                self._observed_phases.add(event.event_type)
        result = {
            "event": event.to_dict(),
            "risk_findings": [finding.to_dict() for finding in findings],
            "persisted": persisted,
        }
        if self.run_resolver is not None:
            result["run"] = self.run_resolver(event.session_id, event.cwd, event.event_type)
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
                if getattr(queue, "needs_snapshot", False):
                    continue
                if queue.full():
                    # A connected client can also lose events under pressure.
                    # Collapse the backlog to one explicit snapshot request.
                    while not queue.empty():
                        queue.get_nowait()
                    queue.needs_snapshot = True
                    queue.put_nowait(None)
                else:
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
                if result is None:
                    queue.needs_snapshot = False
                    yield 'event: reset\ndata: {"reason": "overflow"}\n\n'
                else:
                    yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"
        finally:
            if subscription in self._subscribers:
                self._subscribers.remove(subscription)
