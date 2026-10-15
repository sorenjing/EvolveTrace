"""Strict, provider-neutral contracts for installable personal AI packs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path, PureWindowsPath
import re
from typing import Any, Mapping


_SECRET_KEYS = {"authorization", "cookie", "password", "secret", "token"}
_ENVIRONMENT_NAME = re.compile(r"AICTX_[A-Z0-9_]+\Z")


def _required(value: object, name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _reject_unsafe(value: object, *, key: str = "") -> None:
    if key.lower() in _SECRET_KEYS or key.lower().endswith(("_token", "_secret", "_password")):
        raise ValueError(f"secret field is not allowed: {key}")
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            _reject_unsafe(child, key=str(child_key))
    elif isinstance(value, list):
        for child in value:
            _reject_unsafe(child, key=key)
    elif isinstance(value, str):
        if value.startswith(("/", "~")) or PureWindowsPath(value).is_absolute():
            raise ValueError("local absolute paths are not allowed")


def _load_document(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
    else:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - packaging guarantees it
            raise ValueError("YAML manifests require PyYAML") from exc
        payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError("pack manifest must contain an object")
    return payload


@dataclass(frozen=True)
class DiscoveryConfig:
    strategy: str
    max_depth: int
    workspace_env: str
    portfolio_env: str


@dataclass(frozen=True)
class EntrypointConfig:
    authority: str
    minimum_context: bool
    local: DiscoveryConfig
    codex_enabled: bool
    chatgpt_enabled: bool


def _entrypoints(payload: object) -> EntrypointConfig:
    if not isinstance(payload, dict) or set(payload) != {"common", "local", "codex", "chatgpt"}:
        raise ValueError("entrypoint config fields are invalid")
    common = payload["common"]
    local = payload["local"]
    codex = payload["codex"]
    chatgpt = payload["chatgpt"]
    if not isinstance(common, dict) or set(common) != {"authority", "minimum_context"}:
        raise ValueError("common entrypoint fields are invalid")
    if not isinstance(local, dict) or set(local) != {"discovery"}:
        raise ValueError("local entrypoint fields are invalid")
    if not isinstance(codex, dict) or set(codex) != {"enabled"}:
        raise ValueError("codex entrypoint fields are invalid")
    if not isinstance(chatgpt, dict) or set(chatgpt) != {"enabled"}:
        raise ValueError("chatgpt entrypoint fields are invalid")
    discovery = local["discovery"]
    fields = {"strategy", "max_depth", "workspace_env", "portfolio_env"}
    if not isinstance(discovery, dict) or set(discovery) != fields:
        raise ValueError("discovery config fields are invalid")
    if discovery["strategy"] != "bounded":
        raise ValueError("discovery strategy must be bounded")
    max_depth = discovery["max_depth"]
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or not 0 <= max_depth <= 5:
        raise ValueError("discovery max_depth must be an integer from 0 through 5")
    workspace_env = _required(discovery["workspace_env"], "workspace_env")
    portfolio_env = _required(discovery["portfolio_env"], "portfolio_env")
    if not _ENVIRONMENT_NAME.fullmatch(workspace_env) or not _ENVIRONMENT_NAME.fullmatch(portfolio_env):
        raise ValueError("discovery environment names must use the AICTX_ prefix")
    if not isinstance(common["minimum_context"], bool):
        raise ValueError("minimum_context must be boolean")
    if not isinstance(codex["enabled"], bool) or not isinstance(chatgpt["enabled"], bool):
        raise ValueError("entrypoint enabled flags must be boolean")
    return EntrypointConfig(
        authority=_required(common["authority"], "authority"),
        minimum_context=common["minimum_context"],
        local=DiscoveryConfig("bounded", max_depth, workspace_env, portfolio_env),
        codex_enabled=codex["enabled"],
        chatgpt_enabled=chatgpt["enabled"],
    )


@dataclass(frozen=True)
class PersonalAIPack:
    schema: str
    pack_id: str
    version: int
    profile: dict[str, Any]
    sources: dict[str, Any]
    platforms: dict[str, dict[str, Any]]
    policies: dict[str, Any]
    entrypoints: EntrypointConfig | None = None

    @classmethod
    def load(cls, path: Path) -> "PersonalAIPack":
        payload = _load_document(path)
        base_fields = {"schema", "id", "version", "profile", "sources", "platforms", "policies"}
        schema = payload.get("schema")
        if schema == "personal-ai-pack/v1":
            allowed = base_fields
            expected_version = 1
        elif schema == "personal-ai-pack/v2":
            allowed = base_fields | {"entrypoints"}
            expected_version = 2
        else:
            raise ValueError("unsupported personal AI pack schema or version")
        if set(payload) != allowed:
            raise ValueError("pack manifest fields are invalid")
        _reject_unsafe(payload)
        if payload["version"] != expected_version:
            raise ValueError("unsupported personal AI pack schema or version")
        for name in ("profile", "sources", "platforms", "policies"):
            if not isinstance(payload[name], dict):
                raise ValueError(f"{name} must be an object")
        policies = dict(payload["policies"])
        required_false = (
            "publish_private_sources",
            "capture_prompt_content",
            "accept_memory_automatically",
        )
        if any(policies.get(name) is not False for name in required_false):
            raise ValueError("safe pack policies must be explicitly disabled")
        platforms: dict[str, dict[str, Any]] = {}
        for name, config in payload["platforms"].items():
            if not isinstance(config, dict) or set(config) != {"enabled", "adapter"}:
                raise ValueError("platform config fields are invalid")
            platforms[_required(name, "platform")] = {
                "enabled": bool(config["enabled"]),
                "adapter": _required(config["adapter"], "adapter"),
            }
        return cls(
            schema,
            _required(payload["id"], "id"),
            expected_version,
            dict(payload["profile"]),
            dict(payload["sources"]),
            platforms,
            policies,
            _entrypoints(payload["entrypoints"]) if expected_version == 2 else None,
        )

    @property
    def enabled_platforms(self) -> tuple[str, ...]:
        return tuple(sorted(name for name, config in self.platforms.items() if config["enabled"]))

    def to_public_summary(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "id": self.pack_id,
            "version": self.version,
            "platforms": list(self.enabled_platforms),
        }


@dataclass(frozen=True)
class ExecutionProfile:
    schema: str
    profile_id: str
    platform: str
    harness: str
    adapter: str
    adapter_version: str
    provider: str | None
    model: str | None
    capabilities: tuple[str, ...]
    policy_profile: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ExecutionProfile":
        allowed = {
            "schema", "profile_id", "platform", "harness", "adapter",
            "adapter_version", "provider", "model", "capabilities", "policy_profile",
        }
        if set(payload) != allowed:
            raise ValueError("execution profile contains unknown fields")
        _reject_unsafe(dict(payload))
        if payload["schema"] != "execution-profile/v1":
            raise ValueError("unsupported execution profile schema")
        capabilities = payload["capabilities"]
        if not isinstance(capabilities, list):
            raise ValueError("capabilities must be a list")
        return cls(
            "execution-profile/v1",
            _required(payload["profile_id"], "profile_id"),
            _required(payload["platform"], "platform"),
            _required(payload["harness"], "harness"),
            _required(payload["adapter"], "adapter"),
            _required(payload["adapter_version"], "adapter_version"),
            str(payload["provider"]).strip() if payload.get("provider") else None,
            str(payload["model"]).strip() if payload.get("model") else None,
            tuple(sorted({_required(item, "capability") for item in capabilities})),
            _required(payload["policy_profile"], "policy_profile"),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["capabilities"] = list(self.capabilities)
        return value
