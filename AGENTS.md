<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# EvolveTrace development guide

## Product boundary

EvolveTrace is a local-first AI development harness for context, evidence, and eval-driven workflows. It binds a small Task Contract and a versioned project-context snapshot to evidence exposed by Coding Agent adapters, runs deterministic evaluators, and keeps the final review decision with the human.

It does not run an Agent, expose hidden chain of thought, upload source code, replace repository inspection, or claim to be a complete sandbox. Team collaboration, cloud sync, RAG, general-purpose requirements management, and multi-agent orchestration remain out of scope.

Read `DESIGN.md` before changing product behavior. Treat future milestones as planned, not implemented.

## Current implementation

- `plugin/`: Codex Hook collector with client-side redaction and deterministic PreToolUse safety policy.
- `backend/audit/`: event model, second-pass redaction, deterministic risk rules, and SQLite repository.
- `backend/services/audit_service.py`: deduplication, persistence, session queries, and SSE fan-out.
- `backend/api/routes.py`: loopback-only HTTP conversion.
- `src/app/`: the current session-first Next.js review workbench.
- `start.ps1`: local frontend/backend launcher with system-browser and `-NoBrowser` modes.

Task Contracts, Context Snapshots, Evaluators, Review Decisions, Regression Cases, and single-process distribution are roadmap items until their implementation and tests land.

## Target module boundaries

- `backend/harness/`: Task, Context Snapshot, Run, Evaluation, Review, and Regression domain code.
- `backend/audit/`: immutable execution evidence and safety findings; do not mix task orchestration into audit parsing.
- `backend/services/`: use-case coordination; routes remain thin.
- `src/app/lib/`: versioned frontend API types and clients.
- `src/app/components/`: task-first review workbench components.
- `plugin/`: adapter-only behavior; never turn Hooks into an Agent runner.

## Cross-repository contract

AI Context Kit owns context discovery, freshness, and semantic-memory rendering. EvolveTrace consumes only the versioned `ContextBundle v1` JSON export described in `DESIGN.md`; it must not import `ai_context_kit` Python internals or parse human-facing Markdown.

## Constraints

- Preserve compatibility for the existing `/api/audit/*` event contract.
- Keep all local APIs restricted to loopback clients.
- Never persist raw Hook payloads or live-looking secrets in fixtures.
- Keep routes thin and deterministic analysis outside the HTTP layer.
- Safety rules must be local, deterministic, narrowly scoped, and return fixed explanations without echoing raw command text.
- An imported Context Snapshot is immutable after a Run references it.
- Do not store local absolute paths in portable Context Bundles or Regression Cases.
- Public fixtures must be synthetic and contain no real `.ai/` content, company details, private-repository content, credentials, personal identifiers, or local paths.
- Deterministic evaluators take priority over LLM judges.
- Optional LLM judges require a separately approved design, explicit local configuration, structured evidence references, versioned rubrics, abstention, and gold-label validation.
- High-risk or low-confidence outcomes always require human review.
- Do not add cloud sync, login, team permissions, RAG, Agent execution, multi-agent orchestration, filesystem sandboxing, or command allowlist UI without a new approved design.

## Development sequence

Implement milestones in this order: M0.3 Task & Context, M0.4 Evidence-based Evals, M0.5 Regression Harness, M0.6 optional LLM Judge experiments. The active first-milestone plan is `docs/superpowers/plans/2026-09-09-task-context-milestone.md`.

## Verification

```powershell
cd backend
venv\Scripts\python.exe -m pip install -r requirements-dev.txt
venv\Scripts\python.exe -m pytest -q
cd ..
npm run lint
npm run build
```

When code changes affect startup or packaging, also run `./start.ps1 -NoBrowser` and verify the health endpoints and UI manually on a personal computer.
