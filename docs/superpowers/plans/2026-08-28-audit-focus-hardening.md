# EvolveTrace Audit Focus Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the legacy Agent executor and leave a focused, tested Codex audit workbench.

**Architecture:** Keep the existing Hook collector, audit domain, SQLite repository, audit service, loopback-only API, SSE stream, and current Next.js audit page. Remove modules and dependencies used only by the former Agent executor, then add a replay fixture that exercises the retained event contract end to end.

**Tech Stack:** Python 3.10+, FastAPI, SQLite, pytest, Next.js 16, React 19, TypeScript

**Spec:** `docs/superpowers/specs/2026-08-28-audit-focus-hardening-design.md`

## Global Constraints

- Keep `/api/audit/*` request and response shapes compatible.
- Keep audit routes restricted to loopback clients.
- Do not add LLM, cloud, authentication, or team features.
- Do not invent performance or adoption claims.

---

### Task 1: Make the HTTP surface audit-only

**Files:**
- Modify: `backend/tests/test_audit_api.py`
- Modify: `backend/api/routes.py`
- Modify: `backend/main.py`
- Modify: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`

**Interfaces:**
- Consumes: existing `AuditService` and `require_loopback(request: Request) -> None`
- Produces: `/health` and `/api/audit/*` as the complete HTTP surface

- [ ] **Step 1: Write the failing route-surface test**

```python
def test_application_exposes_only_health_and_audit_routes():
    paths = {route.path for route in app.routes if route.path.startswith(("/api", "/health"))}
    assert paths == {
        "/health",
        "/api/audit/events",
        "/api/audit/sessions",
        "/api/audit/sessions/{session_id}",
        "/api/audit/stream",
    }
```

- [ ] **Step 2: Run the test and confirm it fails because legacy routes remain**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_audit_api.py::test_application_exposes_only_health_and_audit_routes -q -p no:cacheprovider`

- [ ] **Step 3: Reduce `routes.py` and `main.py` to audit concerns**

Remove Agent, admin, tool and LLM configuration models, imports and endpoints. Remove SlowAPI setup because the retained loopback-only ingestion API does not call external paid services.

- [ ] **Step 4: Split runtime and development dependencies**

Keep FastAPI, Uvicorn and python-dotenv in `requirements.txt`; put pytest and httpx in `requirements-dev.txt` using `-r requirements.txt`.

- [ ] **Step 5: Run the focused and complete retained backend tests**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_audit_api.py backend/tests/test_audit_redaction.py backend/tests/test_audit_repository.py backend/tests/test_audit_risk.py backend/tests/test_audit_service.py backend/tests/test_hook_capture.py -q -p no:cacheprovider`

- [ ] **Step 6: Commit**

```text
refactor: make EvolveTrace audit-only
```

### Task 2: Remove legacy source and frontend surface

**Files:**
- Delete: `backend/agent/`
- Delete: `backend/auth/`
- Delete: `backend/tools/`
- Delete: `backend/services/agent_service.py`
- Delete: `backend/services/admin_service.py`
- Delete: `backend/services/config_service.py`
- Delete: `backend/services/tool_service.py`
- Delete: `backend/config.py`
- Delete: `backend/exceptions.py`
- Delete: `backend/logger.py`
- Delete: `backend/session_store.py`
- Delete: `backend/tests/test_code_safety.py`
- Delete: `backend/tests/test_kernel.py`
- Delete: `backend/tests/test_sandbox.py`
- Delete: `src/app/components/ConfigPanel.tsx`
- Delete: `src/app/components/Header.tsx`
- Delete: `src/app/components/InputArea.tsx`
- Delete: `src/app/components/TaskTemplates.tsx`
- Delete: `src/app/components/ThemeToggle.tsx`
- Delete: `src/app/components/Timeline.tsx`
- Delete: `src/app/components/ToolsPanel.tsx`
- Modify: `src/app/lib/types.ts`
- Modify: `package.json`
- Modify: `package-lock.json`

**Interfaces:**
- Consumes: imports used by `src/app/page.tsx` and `src/app/layout.tsx`
- Produces: a source tree in which every remaining module serves the audit workbench

- [ ] **Step 1: Record the retained import set**

Run: `rg -n '^import ' src/app backend/audit backend/api backend/services/audit_service.py backend/main.py`

- [ ] **Step 2: Delete only the listed legacy files**

Keep `ErrorBoundary`, all `Audit*`, `EventInspector`, `ReviewComposer`, `Session*`, `audit-api.ts`, `audit-types.ts`, and the backend audit modules.

- [ ] **Step 3: Trim `types.ts` and JavaScript dependencies**

Retain only the backend URL constant required by `audit-api.ts`. Remove `@ai-sdk/openai`, `ai`, `marked`, and `zod` if `rg` confirms no retained import.

- [ ] **Step 4: Regenerate the lockfile using the bundled Node runtime**

Run the local npm CLI with `--package-lock-only --ignore-scripts`, then inspect the lockfile diff.

- [ ] **Step 5: Verify no legacy symbols remain**

Run: `rg -n 'agent_service|admin_service|tool_service|config_service|AgentKernel|/agent/|/admin/|/tools' backend src`
Expected: no matches.

- [ ] **Step 6: Commit**

```text
refactor: remove legacy agent executor
```

### Task 3: Add reproducible Hook replay evidence and align documentation

**Files:**
- Create: `backend/tests/fixtures/codex_hook_session.json`
- Create: `backend/tests/test_audit_replay.py`
- Modify: `backend/scripts/seed_demo.py`
- Modify: `README.md`
- Modify: `DESIGN.md`
- Modify: `AGENTS.md`
- Modify: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `AuditService.ingest(payload: dict) -> dict`
- Produces: a reusable, already-redacted Hook session fixture and audit-only contributor guidance

- [ ] **Step 1: Add the replay test before the fixture**

The test must load the fixture, ingest every event twice, and assert one stored copy per event, no fixture sentinel secret in serialized session data, and at least one recovered risk finding.

- [ ] **Step 2: Run the test and confirm it fails because the fixture is absent**

Run: `backend/venv/Scripts/python.exe -m pytest backend/tests/test_audit_replay.py -q -p no:cacheprovider`

- [ ] **Step 3: Add the minimal sanitized fixture and reuse it in `seed_demo.py`**

Use Codex event names already accepted by the plugin. Include one failed tool call, one risky command, and a `[REDACTED]` credential value; never include a live-looking secret.

- [ ] **Step 4: Update documentation and CI dependency installation**

Describe only the retained audit architecture. Install `requirements-dev.txt` in CI.

- [ ] **Step 5: Run complete verification**

Run backend tests, Python compileall, frontend lint, and Next.js production build.

- [ ] **Step 6: Commit**

```text
test: add reproducible audit replay
```

