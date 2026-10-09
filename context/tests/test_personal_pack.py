import json
from pathlib import Path

import pytest

from ai_context_kit.personal_pack import ExecutionProfile, PersonalAIPack


def write_pack(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def valid_pack() -> dict:
    return {
        "schema": "personal-ai-pack/v1",
        "id": "example-personal-ai",
        "version": 1,
        "profile": {"visibility": "private", "authority": "portfolio"},
        "sources": {
            "portfolio": {"repository": "example/private-portfolio", "registry": "registry.yaml"},
            "context": {"provider": "ai-context-kit"},
        },
        "platforms": {
            "codex": {"enabled": True, "adapter": "codex-plugin"},
            "chatgpt": {"enabled": True, "adapter": "openai-plugin"},
        },
        "policies": {
            "publish_private_sources": False,
            "capture_prompt_content": False,
            "accept_memory_automatically": False,
        },
    }


def valid_pack_v2() -> dict:
    value = valid_pack()
    value["schema"] = "personal-ai-pack/v2"
    value["version"] = 2
    value["entrypoints"] = {
        "common": {"authority": "portfolio", "minimum_context": True},
        "local": {
            "discovery": {
                "strategy": "bounded",
                "max_depth": 3,
                "workspace_env": "AICTX_WORKSPACE_ROOT",
                "portfolio_env": "AICTX_PORTFOLIO_ROOT",
            }
        },
        "codex": {"enabled": True},
        "chatgpt": {"enabled": True},
    }
    return value


def test_pack_loads_provider_neutral_manifest(tmp_path: Path) -> None:
    pack = PersonalAIPack.load(write_pack(tmp_path / "pack.json", valid_pack()))
    assert pack.pack_id == "example-personal-ai"
    assert pack.enabled_platforms == ("chatgpt", "codex")
    assert pack.to_public_summary() == {
        "schema": "personal-ai-pack/v1",
        "id": "example-personal-ai",
        "version": 1,
        "platforms": ["chatgpt", "codex"],
    }


def test_v1_remains_compatible_without_entrypoints(tmp_path: Path) -> None:
    pack = PersonalAIPack.load(write_pack(tmp_path / "v1.json", valid_pack()))
    assert pack.schema == "personal-ai-pack/v1"
    assert pack.entrypoints is None


def test_v2_loads_strict_entrypoint_contract(tmp_path: Path) -> None:
    pack = PersonalAIPack.load(write_pack(tmp_path / "v2.json", valid_pack_v2()))
    assert pack.schema == "personal-ai-pack/v2"
    assert pack.version == 2
    assert pack.entrypoints is not None
    assert pack.entrypoints.authority == "portfolio"
    assert pack.entrypoints.minimum_context is True
    assert pack.entrypoints.local.max_depth == 3
    assert pack.entrypoints.codex_enabled is True
    assert pack.entrypoints.chatgpt_enabled is True


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["entrypoints"]["local"]["discovery"].update(max_depth=-1),
        lambda value: value["entrypoints"]["local"]["discovery"].update(max_depth=6),
        lambda value: value["entrypoints"]["local"]["discovery"].update(max_depth=True),
        lambda value: value["entrypoints"]["local"]["discovery"].update(strategy="recursive"),
        lambda value: value["entrypoints"]["local"]["discovery"].update(workspace_env="HOME"),
        lambda value: value["entrypoints"]["common"].update(extra=True),
        lambda value: value["entrypoints"].update(extra={}),
    ],
)
def test_v2_rejects_invalid_entrypoint_contract(tmp_path: Path, mutation) -> None:
    payload = valid_pack_v2()
    mutation(payload)
    with pytest.raises(ValueError):
        PersonalAIPack.load(write_pack(tmp_path / "pack.json", payload))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(schema="personal-ai-pack/v2"),
        lambda value: value["policies"].update(publish_private_sources=True),
        lambda value: value["sources"]["portfolio"].update(path=r"C:\private"),
        lambda value: value["sources"]["portfolio"].update(token="secret-value"),
    ],
)
def test_pack_rejects_unsafe_or_unsupported_values(tmp_path: Path, mutation) -> None:
    payload = valid_pack()
    mutation(payload)
    with pytest.raises(ValueError):
        PersonalAIPack.load(write_pack(tmp_path / "pack.json", payload))


def test_execution_profile_excludes_knowledge_and_secret_fields() -> None:
    profile = ExecutionProfile.from_dict(
        {
            "schema": "execution-profile/v1",
            "profile_id": "codex-local",
            "platform": "codex",
            "harness": "codex-work",
            "adapter": "openai-plugin",
            "adapter_version": "1.0.0",
            "provider": "openai",
            "model": "gpt-test",
            "capabilities": ["mcp", "skills", "mcp"],
            "policy_profile": "local-reviewed",
        }
    )
    assert profile.capabilities == ("mcp", "skills")
    with pytest.raises(ValueError, match="unknown"):
        ExecutionProfile.from_dict({**profile.to_dict(), "prompt": "private"})
