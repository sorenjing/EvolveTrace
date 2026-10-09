# Context component consolidation

## Product and ownership

EvolveTrace is the primary repository for project context delivery and coding-agent execution evidence. The context component continues to expose `aictx` and `aictx-mcp` as independently installable commands. Marlow remains an independent compatibility probe tool.

This migration consolidates source, installation, plugin packaging, CI and maintenance documentation. Automatic conversation extraction, semantic retrieval, temporal fact resolution and new workbench views require separate designs and are not delivered by this migration.

## Structure and compatibility

- `context/` contains the AI Context Kit Python package, tests, canonical Skill, examples and component documentation.
- Existing `backend/`, `src/`, `start.ps1` and HTTP contracts retain their paths.
- The backend continues consuming versioned Context Bundles; it does not import context implementation internals.
- The repository-root `.codex-plugin/plugin.json` and `hooks/hooks.json` compose context loading with existing event collection. `context/skills/` is the sole canonical source of the context Skill.
- Existing `plugin/` remains a compatible audit-only package. Its license metadata must match Apache-2.0.
- A standard-library archive builder includes an explicit plugin payload, excluding runtime databases, workspace memory, dependencies and build output. Both plugin hook families must resolve after extraction into a path containing spaces.
- Unified-plugin users enable one installation and disable the previous separate context/audit plugins to avoid duplicate startup loading and capture.
- The context Python package remains `ai-context-kit`, version 0.2.0, Python >=3.11. Wheel Skill data and CLI behavior remain compatible.

## Git history and existing work

Import the committed AI Context Kit tree under `context/`, with both repository histories reachable from the consolidation merge commit. Carry the reviewed local context-loading repair and effectiveness guide into the component. Preserve all original checkout files and unrelated uncommitted changes.

The context component retains its MIT license; EvolveTrace retains Apache-2.0. Record component attribution in the root NOTICE. Imported historical plans and workflows are history; only root GitHub workflows execute in the consolidated repository.

## Remote transition

The canonical destination is `sorenjing/EvolveTrace`, default branch `master`. The legacy `sorenjing/ai-context-kit` repository stays available during migration. Update its public introduction and plugin distribution sources only after the new tree is published and the pinned subdirectory installation is verified. Archive, deletion, repository renaming, tag publication, marketplace edits and PyPI publication are separate release operations.

New Git installs use an explicitly reviewed consolidation commit with `#subdirectory=context`. Local installs use `python -m pip install ./context`. Root CI must test the context component and unified archive. Python release tags use `context-v*` so application tags cannot publish the component accidentally; the new repository needs its own PyPI trusted-publisher configuration.

## Acceptance

1. Both original histories are ancestors of the local merge commit; no original source checkout is deleted.
2. Context and backend suites pass using explicit temporary directories.
3. The context wheel builds and its CLI runs from an isolated installation.
4. The unified plugin archive contains its manifest, hooks, Skill and licenses; referenced commands exist and context loading works after extraction.
5. Existing frontend lint/build and public website build remain usable.
6. Installation, plugin activation, observation and remote migration are explained together, with current capability limits explicit.
