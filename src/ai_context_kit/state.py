"""Versioned fingerprints and project freshness state."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile

from .models import ProjectFacts


STATE_VERSION = 1


class StateError(ValueError):
    """Raised when a persisted state file has an invalid schema."""


@dataclass(frozen=True)
class ProjectState:
    path: str
    fingerprint: str
    rendered_fingerprint: str
    git_commit: str | None = None
    git_branch: str | None = None


@dataclass(frozen=True)
class WorkspaceState:
    projects: dict[str, ProjectState]


def fingerprint_facts(facts: ProjectFacts) -> str:
    """Hash normalized facts and the exact bounded metadata contents."""
    digest = hashlib.sha256()
    normalized = {
        "name": facts.project.name,
        "path": facts.project.relative_path,
        "markers": facts.project.markers,
        "description": facts.description,
        "technologies": facts.technologies,
        "commands": facts.commands,
        "directories": facts.directories,
        "git_branch": facts.git_branch,
        "git_head": facts.git_head,
        "git_dirty": facts.git_dirty,
    }
    digest.update(json.dumps(normalized, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    for relative in facts.scanned_files:
        digest.update(relative.as_posix().encode("utf-8"))
        path = facts.project.path / relative
        try:
            digest.update(path.read_bytes())
        except OSError:
            digest.update(b"<missing>")
    return digest.hexdigest()


def load_state(root: Path, *, strict: bool = False) -> WorkspaceState:
    path = root / ".ai" / "state.json"
    if not path.exists():
        return WorkspaceState({})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("version") != STATE_VERSION:
            raise StateError(f"state version must be {STATE_VERSION}")
        raw_projects = data.get("projects")
        if not isinstance(raw_projects, dict):
            raise StateError("state projects must be an object")
        projects = {}
        for name, value in raw_projects.items():
            commit = value.get("git_commit")
            branch = value.get("git_branch")
            if (commit is not None and not isinstance(commit, str)) or (
                branch is not None and not isinstance(branch, str)
            ):
                raise StateError("state Git fields must be strings or null")
            projects[name] = ProjectState(
                str(value["path"]),
                str(value["fingerprint"]),
                str(value["rendered_fingerprint"]),
                commit,
                branch,
            )
        if not all(isinstance(name, str) for name in projects):
            raise StateError("state project names must be strings")
    except (OSError, json.JSONDecodeError, KeyError, TypeError, StateError) as exc:
        if strict:
            raise StateError(f"invalid state file: {exc}") from exc
        return WorkspaceState({})
    return WorkspaceState(projects)


def _atomic_text(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(contents)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def write_state(root: Path, state: WorkspaceState) -> None:
    data = {
        "version": STATE_VERSION,
        "projects": {
            name: {
                "path": value.path,
                "fingerprint": value.fingerprint,
                "rendered_fingerprint": value.rendered_fingerprint,
                "git_commit": value.git_commit,
                "git_branch": value.git_branch,
            }
            for name, value in sorted(state.projects.items())
        },
    }
    _atomic_text(root / ".ai" / "state.json", json.dumps(data, indent=2, sort_keys=True) + "\n")


def classify_projects(
    facts: list[ProjectFacts], state: WorkspaceState
) -> dict[str, str]:
    current: dict[str, str] = {}
    seen: set[str] = set()
    for item in facts:
        name = item.project.name
        seen.add(name)
        fingerprint = fingerprint_facts(item)
        previous = state.projects.get(name)
        if previous is None:
            current[name] = "new"
        elif previous.rendered_fingerprint != fingerprint:
            current[name] = "stale"
        else:
            current[name] = "current"
    for name in state.projects.keys() - seen:
        current[name] = "missing"
    return dict(sorted(current.items()))
