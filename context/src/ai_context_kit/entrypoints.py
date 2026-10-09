"""Deterministic bootstrap and fallback entrypoints for Personal AI Packs."""

from __future__ import annotations

import json

from . import __version__
from .personal_pack import PersonalAIPack


COMMON_PATH = "generated/common/entry-policy.md"

COMMON_POLICY = f"""# Common entry policy

This file is the shared contract for every generated entrypoint. Read `{COMMON_PATH}` before using a platform adapter.

- Load the minimum task-specific context.
- Treat repository code, tests, and repository rules as implementation facts.
- Use the configured portfolio authority only for cross-project boundaries and routing.
- Do not guess an authority, workspace, repository, or capability.
- Do not load every private source to avoid missing context.
- Distinguish plans from verified implementation.
- Preserve user work and write facts back to their owning authority.
- Report the authority, target repository, freshness, and sources actually used.
"""

LOCAL_ENTRYPOINT = f"""# Local workspace entrypoint

Read `{COMMON_PATH}` and apply its minimum-context, do not guess, and source-reporting rules.

1. Resolve explicit configuration before environment variables and machine-local overrides.
2. Otherwise use bounded discovery from the current directory; never assume a fixed absolute path.
3. Inspect only repository roots and supported marker files. Do not scan a home directory without a bound.
4. If multiple equal candidates remain, report them and ask the user to choose.
5. Report the resolved workspace, authority, target repository, Git state, and sources before mutation.
"""

CODEX_ENTRYPOINT = f"""# Codex entrypoint

Read `{COMMON_PATH}` and apply its minimum-context, do not guess, and source-reporting rules.

1. Read `AGENTS.md`, then `.ai/GLOBAL.md`, `.ai/WORKSPACE.md`, and only the selected project memory.
2. Run `aictx status` and inspect the current branch, worktree, and uncommitted changes.
3. Consult the portfolio only for cross-project routing or decisions.
4. Use current source and tests for behavior; do not inject the whole portfolio into every task.
5. Report ContextBundle identifiers, sources used, and verification evidence when available.
"""

CHATGPT_ENTRYPOINT = f"""# ChatGPT entrypoint

Read `{COMMON_PATH}` and apply its minimum-context, do not guess, and source-reporting rules.

ChatGPT cannot inspect local directories. First identify which source is actually available:

1. registered read-only MCP;
2. authorized GitHub Connector;
3. a reviewed handoff in the ChatGPT Project;
4. otherwise request the minimum necessary files from the user.

Use the portfolio to route to a target repository only after access is confirmed. Report handoff freshness, sources, and unavailable capabilities. Never treat Saved Memory as project fact.
"""

SKILL = f"""---
name: manage-ai-context
description: Load the smallest source-traceable context bundle needed for a project task.
---

# Manage AI Context

Read `{COMMON_PATH}`. Resolve the target project, request the minimum bounded context through AI Context Kit, do not guess missing authorities, and report the bundle and sources used. Never request the full private portfolio by default.
"""


def render_pack_files(pack: PersonalAIPack) -> dict[str, str]:
    """Render managed assets without copying private source mappings."""
    plugin = {
        "name": "ai-context-kit",
        "version": __version__,
        "description": "Load bounded, source-traceable context on demand",
        "skills": "./skills/",
        "platforms": list(pack.enabled_platforms),
        "mcp": {"server": "aictx-mcp", "readOnly": True},
    }
    rendered = {
        COMMON_PATH: COMMON_POLICY,
        "generated/local/local-workspace.md": LOCAL_ENTRYPOINT,
        "generated/openai/plugin.json": json.dumps(plugin, indent=2, sort_keys=True) + "\n",
        "generated/openai/skills/manage-ai-context/SKILL.md": SKILL,
    }
    entrypoints = pack.entrypoints
    if entrypoints is None or entrypoints.codex_enabled:
        rendered["generated/openai/entrypoints/codex.md"] = CODEX_ENTRYPOINT
    if entrypoints is None or entrypoints.chatgpt_enabled:
        rendered["generated/openai/entrypoints/chatgpt.md"] = CHATGPT_ENTRYPOINT
    return rendered
