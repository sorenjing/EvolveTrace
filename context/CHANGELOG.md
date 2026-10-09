# Changelog

## Unreleased

- Add strict `personal-ai-pack/v2` entrypoint and bounded discovery configuration while preserving v1 manifests.
- Generate one common entry policy with thin Local, Codex, and ChatGPT bootstrap/fallback adapters.
- Add `aictx locate` with explicit, environment, untracked-local-override, and bounded-discovery precedence.
- Refuse install, update, or uninstall when a managed Pack asset was modified outside the installer.
- Add `task-envelope/v2` with reviewed multi-repository scope, constraints, and structured acceptance criteria.
- Add `aictx task prepare --contract <path>` with atomic validation and a public-safe example contract.
- Preserve v1 task compatibility while transporting v2 criteria unchanged to EvolveTrace.
- Add provider-neutral Task Envelopes and monotonic Context Receipts.
- Add atomic task-bound context artifacts with bounded, explicit source references.
- Add optional, loopback-only, fail-open EvolveTrace submission.
- Serialize mutating CLI commands with a cross-platform workspace file lock.
- Bound MCP in-flight GitHub reads, request duration, and response size.
- Document the local process model, multi-worker sizing, and failure guarantees.

## 0.2.0 - Unreleased

- Add deterministic, review-before-commit GitHub publication bundles and index.
- Add a read-only GitHub-backed MCP server with `list_projects`, `get_context`, and `get_freshness`.
- Add the portable Agent Plugins manifest, container deployment, and web MVP deployment guide.
- Keep local context collection offline and require explicit publication.

- Add a standard and portable AI Context Kit plugin manifest.
- Keep `manage-ai-context` in the canonical `skills/` directory and Python package artifacts.

All notable changes to AI Context Kit are documented here. The project follows semantic versioning after the first published release.

## 0.1.0 - Unreleased

### Added

- Offline discovery of nested projects from recognized repository markers.
- Deterministic project facts and metadata fingerprints for `current`, `stale`, `new`, and `missing` status.
- Managed context adapters for Codex, Claude, Gemini, and Cursor.
- Byte-preserved manual memory blocks and validation for damaged markers.
- `init`, `scan`, `status`, `update`, and `check` commands with dry-run support for mutations.
- `aictx --version` and a Codex context-management Skill.
- Cross-platform CI for Python 3.11–3.13 on Windows, macOS, and Linux.

### Security boundaries

- No networking, model API, daemon, database, or vector store at runtime.
- No traversal through directory symlinks.
- No reads from common secret files and no writes outside the resolved workspace.

### Known limitations

- Human-readable CLI output only; JSON output is not part of version 0.1.
- PyPI publication and external adoption evidence have not been completed.
