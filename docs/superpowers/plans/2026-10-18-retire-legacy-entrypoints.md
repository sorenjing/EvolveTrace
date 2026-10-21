# Legacy Entrypoint Cleanup Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan in the current checkout.

**Goal:** Use the unified plugin and root Dockerfile as the application packaging entrypoints.

**Architecture:** Retain `plugin/hooks/capture_event.py` and `safety_policy.py` as the canonical audit implementation. Remove only the superseded audit-only packaging and API-only Dockerfile. Context's independent package and optional extensions remain supported.

**Tech Stack:** Python, pytest, JSON, Markdown, Docker, TOML.

**Spec:** `AGENTS.md` product boundaries and `docs/consolidation.md` unified plugin contract.

## Global Constraints

- Preserve existing local changes, Hook payload contracts, collector behavior and safety rules.
- Keep user installations, databases, workspace memory and running services untouched.
- Keep changes local; no commit or publication is part of this cleanup.

## Review Focus

- Unified SessionStart must retain both bounded context loading and audit collection.
- Archive extraction must still resolve every configured Hook script.
- Current documentation must reference root `hooks/hooks.json`; historical plans retain their historical paths.
- Collector and safety scripts must remain in the archive and source tree.
- Deduplicating ignore rules must preserve their matching scope and environment-template exceptions.

### Task 1: Retire superseded packaging

- [x] Delete `plugin/.codex-plugin/plugin.json`, `plugin/hooks/hooks.json`, and `backend/Dockerfile`.
- [x] Redirect the existing configuration and replay checks in `backend/tests/test_hook_capture.py` and `test_audit_replay.py` to the unified plugin, preserving matcher coverage for both SessionStart groups.
- [x] Update current installation, operator and architecture documentation, including `plugin/README.md`; retain a migration note for existing audit-only installations.
- [x] Verify backend Hook/operator tests and extracted unified plugin tests.

### Task 2: Remove stale configuration

- [x] Deduplicate exact `.gitignore` rules without merging differently scoped patterns.
- [x] Replace obsolete isort first-party names with the current backend packages.
- [x] Verify ignore behavior, TOML parsing, current-source references and `git diff --check`.
