# Task & Context Milestone Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build M0.3 so EvolveTrace can create a Task Contract, import an immutable `ContextBundle v1`, bind Codex audit sessions to Runs, and review the relationship from a task-first UI.

**Architecture:** AI Context Kit emits a versioned JSON bundle without exposing internal modules. EvolveTrace validates and snapshots that bundle, stores Task and Run records beside the existing audit database, and correlates sessions through an explicit workspace-scoped active-task lease. Existing `/api/audit/*` behavior remains compatible.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, pytest, Next.js 16.2.9, React 19.2.4, TypeScript 5.

**Spec:** `DESIGN.md`

## Global Constraints

- All services and APIs remain localhost-only.
- Existing `/api/audit/*` request and response behavior remains backward compatible.
- Context snapshots are immutable after a Run references them.
- Portable bundles and fixtures contain no absolute paths, credentials, private repository data, company information, or real `.ai/` content.
- EvolveTrace consumes `ContextBundle v1` JSON and never imports AI Context Kit Python internals.
- This milestone does not add evaluators, LLM calls, Agent execution, cloud sync, login, RAG, or team features.
- Each repository receives its own commit after its tests pass.

---

## Task 1: Add the ContextBundle v1 exporter to AI Context Kit

**Files:**
- Create: `src/ai_context_kit/harness_export.py`
- Modify: `src/ai_context_kit/cli.py`
- Modify: `README.md`
- Test: `tests/test_harness_export.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: existing workspace config, project discovery, state freshness, automatic project facts, manual memory, and `GLOBAL.md`.
- Produces: `build_harness_bundle(workspace: Path, project_name: str, generated_at: datetime | None = None) -> dict[str, object]` and CLI command `aictx export harness <project> --format json --output <path|->`.

- [ ] **Step 1: Write exporter schema tests**

```python
def test_build_harness_bundle_uses_relative_paths_and_v1_schema(workspace):
    bundle = build_harness_bundle(
        workspace,
        "sample-app",
        generated_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )
    assert bundle["schema_version"] == "context-bundle/v1"
    assert bundle["project"] == "sample-app"
    assert bundle["generated_at"] == "2026-09-09T00:00:00+00:00"
    assert bundle["freshness"] in {"current", "stale", "missing", "unknown"}
    assert bundle["repositories"][0]["relative_path"] == "sample-app"
    assert str(workspace) not in json.dumps(bundle)
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `python -m pytest tests/test_harness_export.py -q`

Expected: FAIL because `ai_context_kit.harness_export` does not exist.

- [ ] **Step 3: Implement deterministic bundle construction**

Create `harness_export.py` with:

```python
SCHEMA_VERSION = "context-bundle/v1"

def canonical_json(bundle: dict[str, object]) -> str:
    return json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def build_harness_bundle(
    workspace: Path,
    project_name: str,
    generated_at: datetime | None = None,
) -> dict[str, object]:
    """Return bounded project context using workspace-relative paths only."""
```

Reuse existing config/state/render helpers. Reject unknown projects, convert every path with `Path.relative_to(workspace)`, and never include source file bodies beyond content already allowed by AI Context Kit.

- [ ] **Step 4: Add the CLI route and output semantics**

The parser must accept exactly:

```text
aictx export harness PROJECT --format json --output PATH
aictx export harness PROJECT --format json --output -
```

Write UTF-8 JSON followed by one newline. `-` writes to stdout without changing the workspace. Unsupported formats exit non-zero with an argparse error.

- [ ] **Step 5: Test stdout, file output, unknown projects, and absolute-path absence**

Run: `python -m pytest tests/test_harness_export.py tests/test_cli.py -q`

Expected: PASS.

- [ ] **Step 6: Run the AI Context Kit suite and commit**

```bash
python -m pytest -q
git add src/ai_context_kit/harness_export.py src/ai_context_kit/cli.py tests/test_harness_export.py tests/test_cli.py README.md
git commit -m "feat: export versioned harness context bundles"
```

## Task 2: Add Task, Context Snapshot, and Run persistence to EvolveTrace

**Files:**
- Create: `backend/harness/__init__.py`
- Create: `backend/harness/models.py`
- Create: `backend/harness/repository.py`
- Test: `backend/tests/test_harness_repository.py`

**Interfaces:**
- Consumes: SQLite path conventions from `backend/audit/repository.py`.
- Produces: `TaskContract`, `ContextSnapshot`, `Run`, `HarnessRepository.create_task()`, `import_context_snapshot()`, `create_run()`, `bind_session()`, `get_task()`, and `list_tasks()`.

- [ ] **Step 1: Write model validation tests**

```python
def test_task_cannot_be_ready_with_open_questions():
    with pytest.raises(ValueError, match="open questions"):
        TaskContract.create(
            title="Add verified export",
            goal="Export a stable artifact",
            target_repositories=["sample-app"],
            constraints=[],
            acceptance_criteria=[],
            open_questions=["Which format?"],
            risk_level="normal",
            status="ready",
        )

def test_snapshot_digest_is_stable():
    first = ContextSnapshot.from_bundle({"b": 2, "a": 1}, source="file-import")
    second = ContextSnapshot.from_bundle({"a": 1, "b": 2}, source="file-import")
    assert first.content_digest == second.content_digest
```

- [ ] **Step 2: Run the model tests and confirm they fail**

Run: `cd backend; python -m pytest tests/test_harness_repository.py -q`

Expected: FAIL because `harness.models` does not exist.

- [ ] **Step 3: Implement immutable dataclasses and validation**

Use frozen dataclasses. Define exact enum values from `DESIGN.md`. Canonicalize bundle JSON with `sort_keys=True` and `separators=(",", ":")`, then calculate `sha256(...encode("utf-8")).hexdigest()`.

- [ ] **Step 4: Write repository tests for schema creation and relationships**

```python
def test_run_binds_task_snapshot_and_session(tmp_path):
    repository = HarnessRepository(tmp_path / "harness.db")
    task = repository.create_task(make_task())
    snapshot = repository.import_context_snapshot(make_bundle())
    run = repository.create_run(task.task_id, snapshot.snapshot_id)
    bound = repository.bind_session(run.run_id, "session-1", "sample-app")
    assert bound.task_id == task.task_id
    assert bound.context_snapshot_id == snapshot.snapshot_id
    assert bound.session_id == "session-1"
```

- [ ] **Step 5: Implement additive SQLite tables and indexes**

Create `tasks`, `context_snapshots`, `runs`, `active_task_leases`, and `task_acceptance_criteria`. Use foreign keys, unique `content_digest`, unique non-null `session_id`, and an index on `(task_id, started_at)`. Do not modify or delete existing audit tables.

- [ ] **Step 6: Run repository and existing audit tests, then commit**

```bash
cd backend
python -m pytest tests/test_harness_repository.py tests/test_audit_repository.py -q
git add harness tests/test_harness_repository.py
git commit -m "feat: persist task context and run records"
```

## Task 3: Validate and import Context Bundles through a thin service/API

**Files:**
- Create: `backend/harness/context_bundle.py`
- Create: `backend/services/harness_service.py`
- Modify: `backend/api/routes.py`
- Test: `backend/tests/test_harness_api.py`

**Interfaces:**
- Consumes: `HarnessRepository.import_context_snapshot(bundle, source)`.
- Produces: `validate_context_bundle(payload: dict[str, object]) -> dict[str, object]`, `POST /api/harness/context-snapshots`, `POST /api/harness/tasks`, `GET /api/harness/tasks`, and `GET /api/harness/tasks/{task_id}`.

- [ ] **Step 1: Write API rejection tests**

```python
def test_context_import_rejects_unknown_schema(client):
    response = client.post(
        "/api/harness/context-snapshots",
        json={"schema_version": "context-bundle/v2"},
    )
    assert response.status_code == 422

def test_context_import_rejects_absolute_paths(client):
    bundle = make_bundle()
    bundle["repositories"][0]["relative_path"] = "C:\\private\\repo"
    response = client.post("/api/harness/context-snapshots", json=bundle)
    assert response.status_code == 422
```

- [ ] **Step 2: Run API tests and confirm they fail**

Run: `cd backend; python -m pytest tests/test_harness_api.py -q`

Expected: FAIL with 404 responses.

- [ ] **Step 3: Implement bundle validation**

Require the eight fields in `ContextBundle v1`, parse `generated_at` as timezone-aware ISO 8601, restrict freshness values, reject Unix and Windows absolute paths, enforce a 512 KiB request limit, and pass values through existing `redact_value` before persistence.

- [ ] **Step 4: Implement service and loopback-only routes**

Reuse `require_loopback`. Routes translate HTTP input only; `HarnessService` owns state validation and repository calls. Return 201 for creates, 200 for reads, 404 for unknown task ids, and 422 for invalid transitions or bundles.

- [ ] **Step 5: Run focused and full backend tests, then commit**

```bash
cd backend
python -m pytest tests/test_harness_api.py tests/test_audit_api.py -q
python -m pytest -q
git add harness/context_bundle.py services/harness_service.py api/routes.py tests/test_harness_api.py
git commit -m "feat: import task context through local API"
```

## Task 4: Correlate Codex sessions without running the Agent

**Files:**
- Modify: `backend/harness/repository.py`
- Modify: `backend/services/harness_service.py`
- Modify: `backend/services/audit_service.py`
- Modify: `backend/api/routes.py`
- Test: `backend/tests/test_run_binding.py`

**Interfaces:**
- Consumes: normalized event `cwd`, `session_id`, active-task leases, and existing `AuditService.ingest()`.
- Produces: `activate_task(task_id: str, repository_path: str)`, `resolve_run(session_id: str, cwd: str) -> Run | None`, `POST /api/harness/tasks/{task_id}/activate`, and `GET /api/harness/runs/unbound`.

- [ ] **Step 1: Write binding behavior tests**

```python
def test_first_event_creates_run_for_active_repository(service):
    task = service.create_ready_task(target_repositories=["sample-app"])
    service.activate_task(task.task_id, "sample-app")
    result = service.ingest_audit_event(make_event(session_id="s1", cwd="sample-app"))
    assert result["run"]["task_id"] == task.task_id

def test_unmatched_session_remains_unbound(service):
    result = service.ingest_audit_event(make_event(session_id="s2", cwd="other-app"))
    assert result["run"] is None
    assert service.list_unbound_runs()[0]["session_id"] == "s2"
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd backend; python -m pytest tests/test_run_binding.py -q`

Expected: FAIL because active leases and run resolution are not implemented.

- [ ] **Step 3: Implement normalized workspace matching**

Resolve paths without following symlinks, compare normalized path segments rather than string prefixes, and persist only the Task's configured relative repository identifier in portable fields. A repository may have one active lease; activating another task replaces that lease transactionally.

- [ ] **Step 4: Attach binding after audit persistence**

Keep `AuditService.ingest(payload) -> dict` backward compatible. Add an injected optional run resolver; when configured, append a `run` field to the returned envelope without changing the persisted `AuditEvent` schema.

- [ ] **Step 5: Run audit compatibility and binding tests, then commit**

```bash
cd backend
python -m pytest tests/test_run_binding.py tests/test_audit_service.py tests/test_audit_api.py -q
git add harness/repository.py services/harness_service.py services/audit_service.py api/routes.py tests/test_run_binding.py
git commit -m "feat: bind audit sessions to active tasks"
```

## Task 5: Build the task-first workbench slice

**Files:**
- Create: `src/app/lib/harness-types.ts`
- Create: `src/app/lib/harness-api.ts`
- Create: `src/app/components/TaskList.tsx`
- Create: `src/app/components/TaskOverview.tsx`
- Create: `src/app/components/ContextSnapshotCard.tsx`
- Create: `src/app/components/RunList.tsx`
- Modify: `src/app/page.tsx`
- Modify: `src/app/globals.css`

**Interfaces:**
- Consumes: task/context/run endpoints from Tasks 3 and 4 plus the existing audit client.
- Produces: typed `TaskContract`, `ContextSnapshot`, `Run`, `listTasks()`, `getTask()`, `createTask()`, `importContextSnapshot()`, and a Task-first three-column layout.

- [ ] **Step 1: Define frontend types matching backend JSON exactly**

```typescript
export type TaskStatus = "draft" | "ready" | "active" | "evaluating" | "needs_review" | "needs_fix" | "accepted";
export type Freshness = "current" | "stale" | "missing" | "unknown";

export interface TaskContract {
  task_id: string;
  title: string;
  goal: string;
  target_repositories: string[];
  constraints: string[];
  open_questions: string[];
  risk_level: "normal" | "high" | "destructive";
  context_snapshot_id: string | null;
  status: TaskStatus;
}
```

- [ ] **Step 2: Implement an API client with explicit error payloads**

All methods must use `/api/harness/*`, throw `Error(detail)` for non-2xx responses, and reuse the existing same-origin/loopback assumptions from `audit-api.ts`.

- [ ] **Step 3: Replace the root selection model with Task-first navigation**

The left column lists Tasks and an `Unbound Runs` entry. The center shows Task Contract, Context Snapshot freshness, Runs, and the selected Run's existing `AuditTimeline`. The right column keeps `EventInspector` and `ReviewComposer`. Empty, loading, and API-error states must be visible text, not silent blank regions.

- [ ] **Step 4: Preserve current session review behavior**

Selecting a Run with a session id must call the existing `getAuditSession(session_id)` and subscribe to the existing SSE stream. Selecting an unbound session must render the current session review UI without requiring a Task.

- [ ] **Step 5: Run frontend checks and commit**

```bash
npm run lint
npm run build
git add src/app/lib/harness-types.ts src/app/lib/harness-api.ts src/app/components/TaskList.tsx src/app/components/TaskOverview.tsx src/app/components/ContextSnapshotCard.tsx src/app/components/RunList.tsx src/app/page.tsx src/app/globals.css
git commit -m "feat: add task-first harness workbench"
```

## Task 6: Add an end-to-end synthetic fixture and milestone documentation

**Files:**
- Create: `backend/tests/fixtures/context_bundle_v1.json`
- Create: `backend/tests/fixtures/task_context_run.json`
- Create: `backend/tests/test_task_context_replay.py`
- Modify: `backend/scripts/seed_demo.py`
- Modify: `docs/demo.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Consumes: completed M0.3 APIs and repositories.
- Produces: a fully synthetic Task → Context Snapshot → Run → Audit Event demo that works without a real Codex session.

- [ ] **Step 1: Create synthetic fixtures**

Use only names such as `sample-workspace`, `sample-app`, `src/example.ts`, and `tests/example.test.ts`. The fixture must include one current Context Bundle, one Ready Task, one bound Run, and audit events for a source edit followed by a passing test command.

- [ ] **Step 2: Write the replay assertion**

```python
def test_task_context_run_fixture_replays(seed_service):
    result = seed_service.replay_fixture("fixtures/task_context_run.json")
    assert result["task"]["status"] == "active"
    assert result["context_snapshot"]["freshness"] == "current"
    assert result["run"]["session_id"] == "demo-session"
    assert len(result["audit_session"]["events"]) >= 2
```

- [ ] **Step 3: Extend the demo seeder and documentation**

`seed_demo.py` must reset only the synthetic demo ids, import the Context Bundle, create the Task, activate it, and replay audit events. `docs/demo.md` must label Task & Context as implemented while keeping Evaluators and Regression Cases under roadmap.

- [ ] **Step 4: Run privacy scans and all automated checks**

```bash
rg -n "([A-Za-z]:\\\\|/Users/|/home/|api[_-]?key|token|password|cookie|company|internal)" backend/tests/fixtures docs README.md CHANGELOG.md
cd backend
python -m pytest -q
cd ..
npm run lint
npm run build
```

Expected: privacy scan has no unexplained matches; pytest, lint, and build pass.

- [ ] **Step 5: Commit the milestone**

```bash
git add backend/tests/fixtures/context_bundle_v1.json backend/tests/fixtures/task_context_run.json backend/tests/test_task_context_replay.py backend/scripts/seed_demo.py docs/demo.md README.md CHANGELOG.md
git commit -m "docs: publish task and context milestone demo"
```

## Task 7: Package the workbench as one local service

**Files:**
- Create: `scripts/build_static_ui.ps1`
- Modify: `next.config.ts`
- Modify: `src/app/lib/audit-api.ts`
- Modify: `src/app/lib/harness-api.ts`
- Modify: `backend/main.py`
- Modify: `backend/tests/test_audit_api.py`
- Modify: `start.ps1`
- Modify: `Dockerfile`
- Modify: `.gitignore`
- Modify: `RUN.md`

**Interfaces:**
- Consumes: Next.js static export in `out/`, FastAPI application, existing `/api/*` routes, and SSE.
- Produces: one production URL where FastAPI serves `/api/*`, `/health`, static assets, and the workbench; development mode may still use two hot-reload processes.

- [ ] **Step 1: Write the single-service HTTP test**

```python
def test_built_workbench_is_served_from_root(client, static_ui):
    static_ui.joinpath("index.html").write_text("<h1>EvolveTrace</h1>", encoding="utf-8")
    response = client.get("/")
    assert response.status_code == 200
    assert "EvolveTrace" in response.text

def test_api_routes_win_over_static_fallback(client, static_ui):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the focused test and confirm it fails**

Run: `cd backend; python -m pytest tests/test_audit_api.py -q`

Expected: the new root-page assertion fails because FastAPI does not serve the UI.

- [ ] **Step 3: Switch the frontend to a static export and same-origin API URLs**

Set `output: "export"` in `next.config.ts`. API clients must use `window.location.origin` by default in production and retain an explicit `NEXT_PUBLIC_API_BASE_URL` override for two-process development. SSE must use the same base-resolution function as normal requests.

- [ ] **Step 4: Add the deterministic build-copy script**

`scripts/build_static_ui.ps1` must run `npm ci`, run `npm run build`, remove only the repository-local `backend/static` directory, recreate it, and copy the contents of `out/`. It must resolve every path relative to the script location and stop on the first failed command.

- [ ] **Step 5: Serve static files after API registration**

In `backend/main.py`, register `/api/*` and `/health` first. If `backend/static/index.html` exists, mount `StaticFiles(directory=STATIC_UI_DIR, html=True)` at `/`. If it is absent, keep API startup healthy and return a concise 404 message explaining that the static UI has not been built.

- [ ] **Step 6: Convert the user launcher and container to one runtime process**

`start.ps1` must start only Uvicorn on `127.0.0.1:8001`, wait for `/health`, and open `http://127.0.0.1:8001`. Preserve `-NoBrowser`. The Dockerfile must use a Node build stage for `out/`, copy it into a Python runtime image at `backend/static`, install `backend/requirements.txt`, expose port 8001, and run Uvicorn without reload.

- [ ] **Step 7: Ignore generated output and document development versus user mode**

Add `/out/` and `/backend/static/` to `.gitignore`. `RUN.md` must explain that contributors may use two hot-reload processes, while users and the container use the single FastAPI process with prebuilt assets.

- [ ] **Step 8: Run all checks and commit**

```powershell
./scripts/build_static_ui.ps1
cd backend
venv\Scripts\python.exe -m pytest -q
cd ..
npm run lint
npm run build
./start.ps1 -NoBrowser
```

Expected: one Uvicorn process serves health, API, SSE, and the workbench at `http://127.0.0.1:8001`; no separate Next.js process starts.

```bash
git add scripts/build_static_ui.ps1 next.config.ts src/app/lib/audit-api.ts src/app/lib/harness-api.ts backend/main.py backend/tests/test_audit_api.py start.ps1 Dockerfile .gitignore RUN.md
git commit -m "feat: serve the harness as one local process"
```

## Completion Gate

- [ ] AI Context Kit emits valid `ContextBundle v1` through stdout and file output.
- [ ] EvolveTrace rejects incompatible, oversized, or path-leaking bundles.
- [ ] A Task with open questions cannot become Ready.
- [ ] A Codex session in an active target repository becomes a bound Run.
- [ ] An unmatched session remains reviewable under Unbound Runs.
- [ ] Existing audit ingestion, persistence, SSE, Safety Sentinel, and session UI remain compatible.
- [ ] The task-first page shows Task Contract, context freshness, Runs, and audit evidence.
- [ ] A production build serves UI, API, and SSE from one localhost process.
- [ ] `start.ps1 -NoBrowser` prints the single service URL for Codex Browser.
- [ ] All fixtures are synthetic and the privacy scan is clean.
- [ ] Both repositories pass their complete automated test suites.
