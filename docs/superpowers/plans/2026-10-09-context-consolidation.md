# Context Consolidation Implementation Plan

> **For agentic workers:** Use inline execution for this migration. Preserve existing checkout modifications and verify each deliverable before the local merge commit.

**Goal:** Maintain context delivery and execution evidence in EvolveTrace while keeping the context CLI independently installable.

**Architecture:** Import the context package under `context/`, compose the existing hook adapters in one root plugin, and keep the versioned HTTP handoff between components. Preserve both Git histories and retain the legacy repository throughout release verification.

**Tech Stack:** Python >=3.11, existing Next.js frontend, PowerShell, Git, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-10-09-context-consolidation-design.md`

## Global Constraints

- Keep backend/frontend paths and ContextBundle/HTTP contracts compatible.
- Keep one canonical Skill under `context/skills/`.
- Preserve MIT component licensing and Apache-2.0 application licensing.
- Import neither private workspace memory nor runtime caches/databases.
- Leave remote publication, archive and external plugin configuration changes pending release verification.

## Review Focus

- Plugin extraction paths containing spaces: every quoted command resolves.
- Archive payload: no runtime data, source checkout Git metadata or reparse links.
- CLI packaging: wheel contains the canonical Skill and works without an editable old checkout.
- Release separation: only `context-v*` tags target the context wheel.
- Existing uncommitted changes: retain them outside the migration commit.

## Tasks

- [x] Establish clean test baselines in explicit temporary directories.
- [x] Import committed context tree and overlay reviewed local runtime fixes, with source history retained.
- [x] Add archive behavior tests; observe failure, implement allowlisted builder and unified manifest/hooks, verify extracted context hook.
- [x] Update component installation, root usage/design, CI/release workflow and licensing notices.
- [x] Build wheel and archive; run both suites, frontend checks and website verification.
- [x] Review the staged tree and create a local merge commit with both original parents, excluding pre-existing unrelated changes.
- [x] Verify original histories, CLI migration and final Git state; document pending remote transition.

## Execution notes

- Remote metadata confirmed the application repository is `sorenjing/EvolveTrace`; the local legacy URL redirects from `evolvingAI`.
- Initial pytest runs could not access the system pytest temporary directory. Repeat with migration-owned basetemp paths; do not treat setup errors as product regressions.
- Local merge commit: `468e4eba7163e8b08aefb2ffe48cec951b1b1e0a`, with the original EvolveTrace and ai-context-kit commits as parents. Both histories are ancestors; pre-existing website and other working-tree changes remain outside the commit.
- Context suite: 154 passed, 2 skipped. Backend suite: 81 passed. Unified plugin archive tests: 2 passed, 1 skipped. Skips require Windows symlink privileges; the backend retains its existing Starlette/httpx deprecation warning.
- Frontend lint and production build passed. Context wheel/sdist and the unified plugin archive built successfully. An isolated installation verified the wheel imports and packaged canonical Skill without the old editable checkout. The public website build verified 12 pages, 224 local links and its source archive.
- Independent review found no actionable Critical or Important issue. Existing historical Markdown whitespace and test fixtures were preserved rather than globally rewritten.
- The local `aictx.cmd` launcher now loads `EvolveTrace/context`; `aictx --version` reports 0.2.0. Migration-owned test directories and the temporary wheel installation were removed after verification; deliverable archives remain in `dist/`.
- Local origin now uses `https://github.com/sorenjing/EvolveTrace.git`. No remote push, repository archival, package release, marketplace update or unified-plugin host activation has been performed. These remain the release steps in `docs/consolidation.md`.
