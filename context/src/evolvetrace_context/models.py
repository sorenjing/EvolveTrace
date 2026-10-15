"""Shared immutable data models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .repository_context import RepositoryContext


@dataclass(frozen=True)
class Project:
    name: str
    path: Path
    relative_path: str
    markers: tuple[str, ...]


@dataclass(frozen=True)
class ProjectFacts:
    project: Project
    description: str | None
    technologies: tuple[str, ...]
    commands: tuple[tuple[str, str], ...]
    directories: tuple[str, ...]
    git_branch: str | None
    git_head: str | None
    git_dirty: bool | None
    scanned_files: tuple[Path, ...]
    repository: RepositoryContext | None = None

