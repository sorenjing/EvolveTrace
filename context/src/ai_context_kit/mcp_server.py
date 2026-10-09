"""Read-only MCP surface for GitHub-published project context."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import threading
from typing import Iterator

from .github_store import GitHubBundleStore


class InFlightLimit:
    """Bound concurrent remote reads within one MCP worker process."""

    def __init__(self, maximum: int, timeout: float) -> None:
        if maximum < 1 or timeout < 0:
            raise ValueError("in-flight limit must be positive and timeout non-negative")
        self._semaphore = threading.BoundedSemaphore(maximum)
        self.timeout = timeout

    @contextmanager
    def slot(self) -> Iterator[None]:
        if not self._semaphore.acquire(timeout=self.timeout):
            raise RuntimeError("AI Context Kit is busy; retry shortly")
        try:
            yield
        finally:
            self._semaphore.release()


def _store_from_environment() -> GitHubBundleStore:
    repository = os.environ.get("AICTX_GITHUB_REPOSITORY")
    if not repository:
        raise RuntimeError("AICTX_GITHUB_REPOSITORY is required")
    return GitHubBundleStore(
        repository,
        ref=os.environ.get("AICTX_GITHUB_REF", "main"),
        base_path=os.environ.get("AICTX_GITHUB_PATH", ".ai-context"),
        token=os.environ.get("GITHUB_TOKEN"),
        timeout=int(os.environ.get("AICTX_GITHUB_TIMEOUT", "10")),
        max_response_bytes=int(
            os.environ.get("AICTX_MAX_RESPONSE_BYTES", str(2 * 1024 * 1024))
        ),
    )


def _pack_status_from_environment() -> dict[str, object]:
    path = os.environ.get("AICTX_PACK_STATE")
    if not path:
        raise RuntimeError("AICTX_PACK_STATE is required")
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema") != "personal-ai-pack-installation/v1":
        raise RuntimeError("unsupported Personal AI Pack installation state")
    pack = payload.get("pack")
    managed = payload.get("managed_files")
    if not isinstance(pack, dict) or not isinstance(managed, dict):
        raise RuntimeError("invalid Personal AI Pack installation state")
    return {
        "schema": "personal-ai-pack-installation/v1",
        "pack": {
            "schema": pack.get("schema"),
            "id": pack.get("id"),
            "version": pack.get("version"),
            "platforms": list(pack.get("platforms", [])),
        },
        "managed_file_count": len(managed),
    }


def create_server():
    from mcp.server.mcpserver import MCPServer

    server = MCPServer(
        "ai-context-kit",
        instructions=(
            "Read only explicitly published ContextBundle v1 files. Check freshness before "
            "treating context as current; repository source files remain authoritative."
        ),
    )
    limit = InFlightLimit(
        maximum=int(os.environ.get("AICTX_MAX_IN_FLIGHT", "32")),
        timeout=float(os.environ.get("AICTX_ACQUIRE_TIMEOUT", "0.25")),
    )

    @server.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def list_projects() -> list[dict[str, object]]:
        """List projects explicitly published for remote context access."""
        with limit.slot():
            return _store_from_environment().list_projects()

    @server.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def get_context(project: str) -> dict[str, object]:
        """Get the automatic, manual, and global context for one exact project name."""
        with limit.slot():
            return _store_from_environment().get_context(project)

    @server.tool(annotations={"readOnlyHint": True, "openWorldHint": True})
    def get_freshness(project: str) -> dict[str, object]:
        """Get export time, freshness label, and bounded observation scope for a project."""
        with limit.slot():
            return _store_from_environment().get_freshness(project)

    @server.tool(annotations={"readOnlyHint": True, "openWorldHint": False})
    def get_pack_status() -> dict[str, object]:
        """Get allowlisted installation metadata without source bodies or local paths."""
        return _pack_status_from_environment()

    return server


def entrypoint() -> None:
    create_server().run(
        transport="streamable-http",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8000")),
        streamable_http_path="/mcp",
    )
