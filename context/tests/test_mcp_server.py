import asyncio

import pytest

from ai_context_kit.mcp_server import (
    InFlightLimit,
    _pack_status_from_environment,
    _store_from_environment,
    create_server,
)


def test_store_configuration_comes_from_explicit_environment(monkeypatch) -> None:
    monkeypatch.setenv("AICTX_GITHUB_REPOSITORY", "owner/context")
    monkeypatch.setenv("AICTX_GITHUB_REF", "context")
    monkeypatch.setenv("AICTX_GITHUB_PATH", "published")
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    store = _store_from_environment()

    assert store.repository == "owner/context"
    assert store.ref == "context"
    assert store.base_path == "published"
    assert store.token == "token"


def test_store_configuration_requires_repository(monkeypatch) -> None:
    monkeypatch.delenv("AICTX_GITHUB_REPOSITORY", raising=False)

    with pytest.raises(RuntimeError, match="AICTX_GITHUB_REPOSITORY"):
        _store_from_environment()


def test_server_uses_current_mcp_sdk() -> None:
    from mcp.server.mcpserver import MCPServer

    assert isinstance(create_server(), MCPServer)

    tools = asyncio.run(create_server().list_tools())
    assert [tool.name for tool in tools] == [
        "list_projects", "get_context", "get_freshness", "get_pack_status"
    ]
    assert all(tool.annotations.read_only_hint for tool in tools)


def test_in_flight_limit_rejects_excess_work_instead_of_waiting_forever() -> None:
    limit = InFlightLimit(maximum=1, timeout=0.01)

    with limit.slot():
        with pytest.raises(RuntimeError, match="busy"):
            with limit.slot():
                pytest.fail("request exceeded the in-flight limit")


def test_pack_status_exposes_only_allowlisted_installation_metadata(tmp_path, monkeypatch) -> None:
    state = tmp_path / "state.json"
    state.write_text(
        '{"schema":"personal-ai-pack-installation/v1","pack":{"schema":"personal-ai-pack/v1",'
        '"id":"example","version":1,"platforms":["codex"]},"managed_files":'
        '{"generated/openai/plugin.json":"abc"},"private_path":"/secret"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("AICTX_PACK_STATE", str(state))

    assert _pack_status_from_environment() == {
        "schema": "personal-ai-pack-installation/v1",
        "pack": {
            "schema": "personal-ai-pack/v1",
            "id": "example",
            "version": 1,
            "platforms": ["codex"],
        },
        "managed_file_count": 1,
    }


def test_v2_pack_status_excludes_sources_entrypoints_and_paths(tmp_path, monkeypatch) -> None:
    state = tmp_path / "state.json"
    state.write_text(
        '{"schema":"personal-ai-pack-installation/v1","pack":{'
        '"schema":"personal-ai-pack/v2","id":"example","version":2,'
        '"platforms":["chatgpt","codex"],"sources":{"private":"hidden"},'
        '"entrypoints":{"local":{"path":"/private/path"}}},'
        '"managed_files":{"generated/common/entry-policy.md":"abc"},'
        '"manifest_path":"/private/manifest"}',
        encoding="utf-8",
    )
    monkeypatch.setenv("AICTX_PACK_STATE", str(state))

    result = _pack_status_from_environment()
    rendered = str(result)
    assert result["pack"]["schema"] == "personal-ai-pack/v2"
    assert result["managed_file_count"] == 1
    for forbidden in ("sources", "entrypoints", "/private", "manifest_path"):
        assert forbidden not in rendered
