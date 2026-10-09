"""Read explicitly published ContextBundle files through the GitHub Contents API."""

from __future__ import annotations

import base64
import json
from typing import Callable
from urllib.parse import quote
from urllib.request import Request, urlopen

from .harness_export import SCHEMA_VERSION
from .publish import INDEX_SCHEMA_VERSION


class BundleStoreError(ValueError):
    pass


class GitHubBundleStore:
    def __init__(
        self,
        repository: str,
        *,
        ref: str = "main",
        base_path: str = ".ai-context",
        token: str | None = None,
        timeout: int = 10,
        max_response_bytes: int = 2 * 1024 * 1024,
        opener: Callable = urlopen,
    ) -> None:
        parts = repository.split("/")
        if len(parts) != 2 or not all(parts):
            raise BundleStoreError("repository must use owner/name format")
        if base_path.startswith("/") or ".." in base_path.split("/"):
            raise BundleStoreError("base_path must be repository-relative")
        self.repository = repository
        self.ref = ref
        self.base_path = base_path.strip("/")
        self.token = token
        self.timeout = timeout
        if max_response_bytes < 1:
            raise BundleStoreError("max_response_bytes must be positive")
        self.max_response_bytes = max_response_bytes
        self.opener = opener

    def _read_json(self, relative_path: str) -> dict[str, object]:
        path = "/".join(filter(None, (self.base_path, relative_path)))
        url = (
            f"https://api.github.com/repos/{self.repository}/contents/"
            f"{quote(path, safe='/')}?ref={quote(self.ref, safe='')}"
        )
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "ai-context-kit"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            with self.opener(Request(url, headers=headers), timeout=self.timeout) as response:
                raw = response.read(self.max_response_bytes + 1)
            if len(raw) > self.max_response_bytes:
                raise BundleStoreError(
                    f"GitHub response exceeds {self.max_response_bytes} bytes"
                )
            envelope = json.loads(raw)
            if envelope.get("encoding") != "base64" or not isinstance(envelope.get("content"), str):
                raise BundleStoreError(f"unexpected GitHub response for {relative_path}")
            return json.loads(base64.b64decode(envelope["content"]).decode("utf-8"))
        except BundleStoreError:
            raise
        except Exception as exc:
            raise BundleStoreError(f"cannot read {relative_path} from GitHub: {exc}") from exc

    def _index(self) -> dict[str, object]:
        index = self._read_json("index.json")
        if index.get("schema_version") != INDEX_SCHEMA_VERSION or not isinstance(
            index.get("projects"), list
        ):
            raise BundleStoreError("invalid context bundle index schema")
        return index

    def list_projects(self) -> list[dict[str, object]]:
        return self._index()["projects"]

    def get_context(self, project: str) -> dict[str, object]:
        entry = next(
            (item for item in self.list_projects() if isinstance(item, dict) and item.get("project") == project),
            None,
        )
        if entry is None:
            raise BundleStoreError(f"unknown project: {project}")
        path = entry.get("path")
        if not isinstance(path, str) or not path.startswith("projects/") or ".." in path.split("/"):
            raise BundleStoreError("invalid project bundle path")
        bundle = self._read_json(path)
        if bundle.get("schema_version") != SCHEMA_VERSION or bundle.get("project") != project:
            raise BundleStoreError("invalid context bundle schema or identity")
        return bundle

    def get_freshness(self, project: str) -> dict[str, object]:
        bundle = self.get_context(project)
        return {
            "project": project,
            "freshness": bundle.get("freshness"),
            "generated_at": bundle.get("generated_at"),
            "observed_scope": bundle.get("observed_scope", []),
        }
