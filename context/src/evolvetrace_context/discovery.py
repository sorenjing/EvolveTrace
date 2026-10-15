"""Deterministic project discovery."""

from __future__ import annotations

import os
from pathlib import Path
import stat

from .config import Config
from .models import Project


MARKERS = (
    ".git",
    "pyproject.toml",
    "setup.py",
    "requirements.txt",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
)


def _relative(root: Path, path: Path) -> str:
    value = path.relative_to(root).as_posix()
    return value or "."


def _contains_symlink(root: Path, candidate: Path) -> bool:
    """Return whether any path component below *root* is a symlink."""
    try:
        parts = candidate.relative_to(root).parts
    except ValueError:
        return True
    current = root
    for part in parts:
        current = current / part
        if _is_link(current):
            return True
    return False


def _is_link(path: Path) -> bool:
    """Reject symlinks and Windows reparse points, including on Python 3.11."""
    if path.is_symlink():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def discover_projects(config: Config) -> list[Project]:
    """Find project roots below configured include paths without following links."""
    found: dict[str, Project] = {}
    root = config.root.resolve()
    for include in config.include:
        candidate = root / include
        if _contains_symlink(root, candidate):
            continue
        start = candidate.resolve()
        try:
            start.relative_to(root)
        except ValueError:
            continue
        if not start.is_dir() or _is_link(start):
            continue
        for current_text, dirs, files in os.walk(start, followlinks=False):
            current = Path(current_text)
            names = set(files) | set(dirs)
            dirs[:] = sorted(
                name
                for name in dirs
                if name not in config.exclude and not _is_link(current / name)
            )
            markers = tuple(marker for marker in MARKERS if marker in names)
            if not markers:
                continue
            relative = _relative(root, current)
            parent_projects = [
                item for item in found.values() if current != item.path and current.is_relative_to(item.path)
            ]
            has_git = ".git" in markers
            if parent_projects and not has_git:
                dirs[:] = []
                continue
            name = config.project_names.get(relative, current.name or root.name)
            found[relative] = Project(name, current.resolve(), relative, markers)
            if not has_git:
                dirs[:] = [name for name in dirs if name != ".git"]
    return [found[key] for key in sorted(found, key=lambda value: (value != ".", value))]
