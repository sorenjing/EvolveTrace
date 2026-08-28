<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# EvolveTrace development guide

## Product boundary

EvolveTrace is a local review and observability workbench for Coding Agent events. It consumes evidence exposed by Codex Hooks; it does not run an Agent, call an LLM, expose hidden chain of thought, or upload source code.

## Architecture

- `plugin/`: best-effort Hook collector with client-side redaction.
- `backend/audit/`: event model, second-pass redaction, deterministic risk rules, and SQLite repository.
- `backend/services/audit_service.py`: deduplication, persistence, session queries, and SSE fan-out.
- `backend/api/routes.py`: loopback-only HTTP conversion.
- `src/app/`: the Next.js review workbench.

## Constraints

- Preserve the `/api/audit/*` event contract.
- Keep audit endpoints restricted to loopback clients.
- Never persist raw Hook payloads or live-looking secrets in fixtures.
- Keep routes thin and deterministic analysis outside the HTTP layer.
- Do not add Agent execution, LLM analysis, cloud sync, login, or team permissions without a new design.

## Verification

```powershell
cd backend
venv\Scripts\python.exe -m pip install -r requirements-dev.txt
venv\Scripts\python.exe -m pytest -q
cd ..
npm run lint
npm run build
```
