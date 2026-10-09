"""Versioned context exports for local AI development harnesses."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

from .config import ConfigError, load_config
from .discovery import discover_projects
from .facts import extract_facts
from .render import _automatic, _manual_content, slugify
from .repository_context import evaluate_freshness
from .state import classify_projects, load_state
from .task_contracts import TaskEnvelope, TaskEnvelopeV2, canonical_digest


SCHEMA_VERSION = "context-bundle/v1"


def _select_project(root: Path, selected: str):
    config = load_config(root)
    matches = [
        extract_facts(project, config)
        for project in discover_projects(config)
        if project.name == selected or slugify(project.name) == selected
    ]
    if not matches:
        raise ConfigError(f"unknown project: {selected}")
    return matches[0]


def _relative_path(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ConfigError("project path must be workspace-relative")
    return path.as_posix()


def build_harness_bundle(
    workspace: Path,
    project_name: str,
    *,
    generated_at: datetime | None = None,
    task: TaskEnvelope | TaskEnvelopeV2 | None = None,
    skill_ids: tuple[str, ...] = (),
    repository_paths: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Build one immutable, portable context bundle from bounded observations."""

    root = workspace.resolve()
    facts = _select_project(root, project_name)
    selected_facts = [facts]
    if repository_paths is not None:
        config_for_discovery = load_config(root)
        by_path = {item.project.relative_path: item for item in (extract_facts(project, config_for_discovery) for project in discover_projects(config_for_discovery))}
        try:
            selected_facts = [by_path[_relative_path(path)] for path in repository_paths]
        except KeyError as exc:
            raise ConfigError(f"unknown target repository: {exc.args[0]}") from exc
    memory_path = root / ".ai" / "projects" / f"{slugify(facts.project.name)}.md"
    global_path = root / ".ai" / "GLOBAL.md"
    project_memory = memory_path.read_text(encoding="utf-8") if memory_path.exists() else None
    global_context = global_path.read_text(encoding="utf-8") if global_path.exists() else ""
    state = load_state(root)
    freshness_states = classify_projects(selected_facts, state)
    freshness = freshness_states[facts.project.name]
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("generated_at must include a timezone")

    config = load_config(root)
    sources: list[dict[str, str]] = []
    for configured in config.context_sources.get(facts.project.name, ()):
        relative = _relative_path(configured)
        source_path = (root / relative).resolve()
        if not source_path.is_relative_to(root):
            raise ConfigError("context source path must be workspace-relative")
        try:
            source_bytes = source_path.read_bytes()
        except OSError as exc:
            raise ConfigError(f"cannot read context source: {relative}") from exc
        if len(source_bytes) > config.max_file_bytes:
            raise ConfigError(f"context source exceeds max_file_bytes: {relative}")
        sources.append(
            {
                "source_id": f"project:{facts.project.name}:{relative}",
                "relative_path": relative,
                "content_digest": hashlib.sha256(source_bytes).hexdigest(),
                "authority": "project",
            }
        )

    repositories = []
    for item in selected_facts:
        record: dict[str, object] = {"name": item.project.name, "relative_path": _relative_path(item.project.relative_path)}
        if item.repository is not None:
            previous = state.projects.get(item.project.name)
            record["source"] = {
                "type": "git",
                "repository": item.repository.repository_name,
                "branch": previous.git_branch if previous else None,
                "commit": previous.git_commit if previous else None,
                "path": _relative_path(item.project.relative_path),
            }
            record["head_commit"] = item.repository.head_commit
            record["context_freshness"] = evaluate_freshness(
                previous.git_commit if previous else None, item.repository
            ).to_dict()
            record["upstream"] = item.repository.upstream
            record["ahead"] = item.repository.ahead
            record["behind"] = item.repository.behind
        repositories.append(record)

    bundle: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "project": facts.project.name,
        "generated_at": timestamp.isoformat(),
        "freshness": freshness,
        "observed_scope": [f"{item.project.relative_path}/{path.as_posix()}" for item in selected_facts for path in item.scanned_files],
        "repositories": repositories,
        "context": {
            "automatic": _automatic(facts).strip(),
            "manual": _manual_content(project_memory).strip(),
            "global": global_context.strip(),
            "related_projects": {
                item.project.name: {
                    "automatic": _automatic(item).strip(),
                    "manual": _manual_content((root / ".ai" / "projects" / f"{slugify(item.project.name)}.md").read_text(encoding="utf-8") if (root / ".ai" / "projects" / f"{slugify(item.project.name)}.md").exists() else None).strip(),
                    "freshness": freshness_states[item.project.name],
                }
                for item in selected_facts if item.project.name != facts.project.name
            },
        },
    }
    if task is not None:
        rendered_context = bundle["context"]
        sources.insert(
            0,
            {
                "source_id": f"context:{facts.project.name}:rendered",
                "relative_path": f".ai/projects/{slugify(facts.project.name)}.md",
                "content_digest": canonical_digest(rendered_context),
                "authority": "project",
            },
        )
        bundle.update(
            {
                "task": {"task_id": task.task_id},
                "sources": sources,
                "skill_ids": list(dict.fromkeys(skill_ids)),
                "conflicts": [],
            }
        )
        digest = canonical_digest(bundle)
        bundle["content_digest"] = digest
        bundle["bundle_id"] = f"ctx_{digest[:24]}"
    return bundle
