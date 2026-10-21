"""Thin entry files for supported AI coding tools."""

from __future__ import annotations

from pathlib import Path

from .state import _atomic_text


MANAGED = "<!-- aictx:managed -->"


class ManagedFileError(ValueError):
    """Raised instead of overwriting a user-owned entry file."""


def context_instructions(tool: str, *, cursor: bool = False) -> str:
    frontmatter = "---\ndescription: Shared AI workspace context\nalwaysApply: true\n---\n" if cursor else ""
    return frontmatter + f"""{MANAGED}
# Shared context for {tool}

Before broad repository analysis:

1. Find the nearest ancestor containing `.aictx.toml`; use that directory as the workspace root, even when working in a nested repository.
2. Run `aictx load <project> --workspace <workspace-root>` to return `.ai/GLOBAL.md`, `.ai/WORKSPACE.md`, and only `.ai/projects/<project>.md`. If a matching SessionStart already returned these sources, inspect that output instead of loading twice.
3. Inspect `aictx usage <project> --workspace <workspace-root>` for returned sources and gaps. Output does not prove host acceptance, model use, or benefit. If the CLI is unavailable, read those same files manually and report that no CLI loading receipt exists.
4. Run `aictx status --workspace <workspace-root>` and inspect source only when that project is stale or the task requires it.
5. Preserve managed markers. Record semantic memory only inside the manual block.
6. Store decisions and current state, not source copies or chat transcripts.
"""


def render_adapters() -> dict[Path, str]:
    return {
        Path("AGENTS.md"): context_instructions("Codex"),
        Path("CLAUDE.md"): context_instructions("Claude"),
        Path("GEMINI.md"): context_instructions("Gemini"),
        Path(".cursor/rules/ai-context.mdc"): context_instructions("Cursor", cursor=True),
    }


def write_managed_file(path: Path, contents: str, *, dry_run: bool) -> bool:
    existing = path.read_text(encoding="utf-8") if path.exists() else None
    if existing is not None and MANAGED not in existing:
        raise ManagedFileError(f"refusing to overwrite user-owned file: {path}")
    if existing == contents:
        return False
    if not dry_run:
        _atomic_text(path, contents)
    return True
