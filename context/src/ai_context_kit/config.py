"""Workspace discovery and configuration loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


DEFAULT_EXCLUDES = (
    ".git",
    ".ai",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    "coverage",
    "__pycache__",
)


class ConfigError(ValueError):
    """Raised when workspace configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    root: Path
    max_file_bytes: int = 1_048_576
    include: tuple[str, ...] = (".",)
    exclude: tuple[str, ...] = DEFAULT_EXCLUDES
    project_names: dict[str, str] | None = None
    context_sources: dict[str, tuple[str, ...]] | None = None

    def __post_init__(self) -> None:
        if self.project_names is None:
            object.__setattr__(self, "project_names", {})
        if self.context_sources is None:
            object.__setattr__(self, "context_sources", {})


def find_workspace(start: Path) -> Path:
    """Find the nearest configured workspace at or above *start*."""
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".aictx.toml").is_file():
            return candidate
    raise ConfigError(f"no .aictx.toml found from {start}")


def _string_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ConfigError(f"{field} must be an array of strings")
    return tuple(value)


def load_config(root: Path) -> Config:
    """Load and validate `.aictx.toml` from *root*."""
    path = root.resolve() / ".aictx.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"cannot load {path}: {exc}") from exc

    if data.get("version") != 1:
        raise ConfigError("configuration version must be 1")
    max_file_bytes = data.get("max_file_bytes", 1_048_576)
    if not isinstance(max_file_bytes, int) or isinstance(max_file_bytes, bool) or max_file_bytes <= 0:
        raise ConfigError("max_file_bytes must be a positive integer")

    discovery = data.get("discovery", {})
    projects = data.get("projects", {})
    context_sources = data.get("context_sources", {})
    if not all(isinstance(value, dict) for value in (discovery, projects, context_sources)):
        raise ConfigError("discovery, projects, and context_sources must be tables")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in projects.items()):
        raise ConfigError("project names must map paths to strings")
    parsed_context_sources = {
        key: _string_tuple(value, f"context_sources.{key}")
        for key, value in context_sources.items()
        if isinstance(key, str)
    }
    if len(parsed_context_sources) != len(context_sources):
        raise ConfigError("context source project names must be strings")

    return Config(
        root=root.resolve(),
        max_file_bytes=max_file_bytes,
        include=_string_tuple(discovery.get("include", ["."]), "discovery.include"),
        exclude=_string_tuple(discovery.get("exclude", list(DEFAULT_EXCLUDES)), "discovery.exclude"),
        project_names=dict(projects),
        context_sources=parsed_context_sources,
    )
