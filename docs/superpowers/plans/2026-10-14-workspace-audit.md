# Workspace audit implementation plan

> Execute inline in the existing clean checkout, as requested by the user.

**Goal:** Cross-project command statistics, evidence-linked anomaly review and
human-confirmed audit memory, discovered and recalled through Context.

**Spec:** ../specs/2026-10-14-workspace-audit-design.md

**Architecture:** A versioned index connects Context discovery to the audit
service. On-demand deterministic analytics read sanitized SQLite evidence;
reviewed notes and notification preferences are the only new mutable state.

## Constraints and review focus

- Preserve existing audit and ContextBundle v1 APIs, loopback access and redaction.
- Keep unknown coverage explicit; no raw data, model execution or disk diagnosis.
- Workspace/project isolation, nested paths, incomplete and replayed events.
- Quote-sensitive command fingerprints, successful retries and captured edits.
- Bound queries and exports; deletion must remove notes referencing lost evidence.
- Project-specific memory only, explicit saving, fail-open optional retrieval.

## Tasks

- [x] 1. Write failing analytic tests; implement pure pairing/classification and
  rule v1 in `backend/audit/activity.py`. Verify no double counts or false
  hardware conclusions; unknown/compound commands remain explicit.
- [x] 2. Write failing API tests; add `backend/audit/workspace.py` persistence,
  `backend/services/activity_service.py` coordination and loopback routes.
  Verify idempotent registry, nested matching, bounded reports, preferences,
  human notes, evidence validation, redaction, restart and deletion behavior.
- [x] 3. Write failing Context tests; implement `audit_client.py`, CLI sync,
  report, memory and remember, plus optional `load --audit-url` recall. Verify
  versioned interchange, no semantic file changes and unavailable-sink behavior.
- [x] 4. Add typed client and project activity panel, opt-in analysis dialog and
  explicit reviewed-note save. Verify frontend lint/build and local UI flow.
- [x] 5. Update design/operator docs and run full backend/Context suites,
  existing frontend checks, static build and final diff review.

## Execution record

- Scope ruling: OS sensors/native Codex modals are deferred; the first release
  exposes actual command evidence and an EvolveTrace analysis dialog.
- Scope ruling: reviewed audit memory stays in SQLite and is optionally recalled
  through Context; existing .ai manual knowledge is never changed automatically.
- Validation: backend 101 passed; Context in its independent development
  environment 162 passed, 2 skipped; frontend 3 tests passed, lint and production
  static build passed. The shared context marker check passed.
- Review: independently reproduced and fixed attached quoted argument identity,
  edit-interleaved failure streaks, and untimed success barriers. The reviewer
  rechecked the fixes, ran 12 analytic tests and found no remaining P1/P2 issues
  in those fixes.
- Synthetic browser smoke test: paired 16 events into 8 observations, verified
  analysis dialog, confirmation-gated note save, mute/unmute and persisted CLI
  recall; continuous SSE updates refreshed statistics. Static workbench copied
  to the local serving directory. Preview data and screenshot remain ignored.
