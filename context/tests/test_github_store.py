import base64
import json

import pytest

from ai_context_kit.github_store import BundleStoreError, GitHubBundleStore


class FakeResponse:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size: int = -1) -> bytes:
        data = json.dumps(self.payload).encode()
        return data if size < 0 else data[:size]


def encoded(value: object) -> dict[str, str]:
    raw = json.dumps(value).encode()
    return {"encoding": "base64", "content": base64.b64encode(raw).decode()}


def test_list_projects_and_get_context_use_bounded_github_paths() -> None:
    calls = []
    index = {
        "schema_version": "context-bundle-index/v1",
        "projects": [
            {
                "project": "demo",
                "path": "projects/demo.json",
                "schema_version": "context-bundle/v1",
                "generated_at": "2026-09-11T00:00:00+00:00",
            }
        ],
    }
    bundle = {
        "schema_version": "context-bundle/v1",
        "project": "demo",
        "generated_at": "2026-09-11T00:00:00+00:00",
        "freshness": "current",
        "observed_scope": ["README.md"],
        "repositories": [],
        "context": {"automatic": "A", "manual": "M", "global": "G"},
    }

    def opener(request, timeout):
        calls.append((request.full_url, dict(request.header_items()), timeout))
        return FakeResponse(encoded(index if request.full_url.endswith("index.json?ref=main") else bundle))

    store = GitHubBundleStore("owner/context", token="secret", opener=opener)

    assert store.list_projects() == index["projects"]
    assert store.get_context("demo") == bundle
    assert calls[0][0] == "https://api.github.com/repos/owner/context/contents/.ai-context/index.json?ref=main"
    assert calls[2][0].endswith("/.ai-context/projects/demo.json?ref=main")
    assert calls[0][1]["Authorization"] == "Bearer secret"
    assert all(timeout == 10 for _, _, timeout in calls)


def test_get_context_rejects_project_not_declared_by_index() -> None:
    index = {"schema_version": "context-bundle-index/v1", "projects": []}
    store = GitHubBundleStore("owner/context", opener=lambda *_args, **_kwargs: FakeResponse(encoded(index)))

    with pytest.raises(BundleStoreError, match="unknown project"):
        store.get_context("../secret")


def test_invalid_index_schema_is_rejected() -> None:
    store = GitHubBundleStore(
        "owner/context",
        opener=lambda *_args, **_kwargs: FakeResponse(encoded({"schema_version": "wrong"})),
    )

    with pytest.raises(BundleStoreError, match="index schema"):
        store.list_projects()


def test_response_larger_than_configured_limit_is_rejected() -> None:
    store = GitHubBundleStore(
        "owner/context",
        max_response_bytes=20,
        opener=lambda *_args, **_kwargs: FakeResponse({"content": "x" * 100}),
    )

    with pytest.raises(BundleStoreError, match="response exceeds 20 bytes"):
        store.list_projects()
