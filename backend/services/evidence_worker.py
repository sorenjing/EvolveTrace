"""Bounded, retryable local metadata reconciliation, independent of UI requests."""

import asyncio
import threading
import time
from datetime import datetime, timezone

from audit.workspace import WorkspaceRepository
from audit.execution_context import FILE_LIMIT
from services.execution_evidence import resolve_execution_evidence


class ExecutionEvidenceWorker:
    def __init__(self, repository: WorkspaceRepository, *, interval: float = 10, batch_size: int = 128):
        self.repository = repository
        self.interval = interval
        self.batch_size = batch_size
        self._task = None
        self._stop = asyncio.Event()
        self._lock = threading.Lock()
        self._status = {"state": "stopped", "last_completed_at": None, "attempted": 0, "resolved": 0,
                        "pending": None, "last_error": None, "batch_limit": batch_size}

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def tick(self, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        candidates = self.repository.pending_execution_evidence(now, self.batch_size)
        # The parser has a separate file budget. Select files in due order
        # before invoking it, so skipped files retain their place in the queue.
        files = set()
        events = []
        for event in candidates:
            key = (event["session_id"], event["details"]["transcript_path"])
            if key not in files and len(files) == FILE_LIMIT:
                continue
            files.add(key)
            events.append(event)
        if events:
            resolve_execution_evidence(events, self.repository)
            self.repository.defer_execution_evidence([event["event_id"] for event in events], now)
        resolved = self.repository.execution_results([event["event_id"] for event in events])
        result = {"attempted": len(events), "resolved": len(resolved),
                  "pending": self.repository.pending_execution_count()}
        with self._lock:
            self._status.update(result, last_completed_at=datetime.now(timezone.utc).isoformat(), last_error=None)
        return result

    async def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop = asyncio.Event()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task

    async def _run(self) -> None:
        try:
            while not self._stop.is_set():
                with self._lock:
                    self._status["state"] = "running"
                try:
                    # File and SQLite access must not block Hook ingress or SSE.
                    await asyncio.to_thread(self.tick)
                except Exception:
                    with self._lock:
                        self._status.update(state="error", last_error="reconciliation_failed")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
                except asyncio.TimeoutError:
                    pass
        finally:
            with self._lock:
                self._status["state"] = "stopped"
