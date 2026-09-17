# Evidence Evaluation Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate structured task criteria against persisted Context, Run, changed-file, command-result, and human-review evidence, then prove a failed-and-corrected two-repository workflow.

**Architecture:** Extend the harness domain with immutable criteria, evaluation results, and review decisions. Keep evaluators pure and deterministic in `backend/harness/evaluators.py`, persistence in `HarnessRepository`, orchestration in `HarnessService`, and routes thin. SQLite remains the source of truth; SSE and UI are read surfaces only.

**Tech Stack:** Python 3, FastAPI, SQLite, pytest, Next.js 16, React 19, TypeScript

**Spec:** `docs/superpowers/specs/2026-09-17-evidence-eval-vertical-slice-design.md`

## Global Constraints

- Preserve `/api/audit/*` and legacy string acceptance criteria.
- Accept `task-envelope/v2` structured criteria without importing AI Context Kit internals.
- Deterministic evaluators never use an LLM.
- Missing evidence is not success.
- Evaluators cannot mark a Task accepted; a human owns the final decision.
- Context Receipts advance exactly one level and never regress.
- A single successful Run cannot automatically become `effective`.
- Keep APIs loopback-only and raw Hook payloads out of SQLite.
- Public fixtures are synthetic and contain no secrets, private content, personal identifiers, or absolute paths.

---

### Task 1: Add structured criteria and immutable evaluation domain types

**Files:**
- Modify: `backend/harness/models.py`
- Modify: `backend/tests/test_harness_repository.py`
- Create: `backend/tests/test_evaluation_models.py`

**Interfaces:**
- Produces: `AcceptanceCriterion.from_payload(payload: Mapping[str, Any]) -> AcceptanceCriterion`
- Produces: `EvaluationResult.create(...) -> EvaluationResult`
- Produces: `ReviewDecision.create(...) -> ReviewDecision`
- Changes: `TaskContract.acceptance_criteria: tuple[str | AcceptanceCriterion, ...]`

- [ ] **Step 1: Write failing model tests**

Cover a valid `command_exit_zero` criterion, duplicate criterion IDs, unknown type/config, traversal/absolute paths, valid evaluation status/severity, and immutable review decisions.

- [ ] **Step 2: Run the tests and verify failure**

Run: `cd backend && python -m pytest tests/test_evaluation_models.py -q`  
Expected: FAIL because the new domain types do not exist.

- [ ] **Step 3: Implement domain constants and frozen dataclasses**

Use:

```python
CRITERION_TYPES = frozenset({"command_exit_zero", "path_scope", "file_exists", "manual"})
EVALUATION_STATUSES = frozenset({"passed", "failed", "needs_review", "skipped"})
EVALUATION_SEVERITIES = frozenset({"info", "warning", "blocking"})
REVIEW_OUTCOMES = frozenset({"accepted", "needs_fix", "blocked"})
```

Keep legacy strings on read and serialize structured criteria as dictionaries. Reject unknown fields before constructing objects.

- [ ] **Step 4: Make model tests pass**

Run: `cd backend && python -m pytest tests/test_evaluation_models.py tests/test_harness_repository.py -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/harness/models.py backend/tests/test_evaluation_models.py backend/tests/test_harness_repository.py
git commit -m "feat: define harness evaluation domain"
```

### Task 2: Persist criteria, evaluations, and review decisions

**Files:**
- Modify: `backend/harness/repository.py`
- Modify: `backend/tests/test_harness_repository.py`

**Interfaces:**
- Produces: `save_evaluation(result: EvaluationResult) -> EvaluationResult`
- Produces: `list_evaluations(task_id: str, run_id: str) -> list[EvaluationResult]`
- Produces: `save_review_decision(decision: ReviewDecision) -> ReviewDecision`
- Produces: `get_review_decision(task_id: str, run_id: str) -> ReviewDecision | None`

- [ ] **Step 1: Write failing repository tests**

Create a task and run, save one result, repeat the same write, and assert one row. Submit a conflicting payload with the same immutable identity and assert rejection. Repeat for Review Decision.

- [ ] **Step 2: Run repository tests and verify failure**

Run: `cd backend && python -m pytest tests/test_harness_repository.py -q`  
Expected: FAIL because persistence methods and tables are missing.

- [ ] **Step 3: Add SQLite tables and row converters**

Use a stable uniqueness key of `(task_id, run_id, criterion_id, evaluator_id, evaluator_version)`. Store `evidence_refs` as JSON. Review Decisions store the exact ordered evaluation IDs they reviewed and reject a second conflicting decision.

- [ ] **Step 4: Preserve existing database compatibility**

Use `CREATE TABLE IF NOT EXISTS` and additive schema changes. If the existing task table stores acceptance criteria JSON, decode both strings and structured dictionaries without rewriting old rows.

- [ ] **Step 5: Run repository and existing harness tests**

Run: `cd backend && python -m pytest tests/test_harness_repository.py tests/test_harness_api.py tests/test_run_binding.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/harness/repository.py backend/tests/test_harness_repository.py
git commit -m "feat: persist evaluation and review evidence"
```

### Task 3: Implement pure deterministic evaluators

**Files:**
- Create: `backend/harness/evaluators.py`
- Create: `backend/tests/test_evaluators.py`

**Interfaces:**
- Produces: `evaluate_context_freshness(task, snapshot, run) -> list[EvaluationResult]`
- Produces: `evaluate_repository_scope(task, changed_paths, run) -> list[EvaluationResult]`
- Produces: `evaluate_verification(task, command_events, run) -> list[EvaluationResult]`
- Produces: `evaluate_file_exists(task, workspace_root, run) -> list[EvaluationResult]`

- [ ] **Step 1: Write table-driven failing tests**

Include current/stale/unknown snapshots; allowed/out-of-scope/traversal paths; successful/failed/missing commands; existing/missing files; and a manual criterion returning `needs_review`.

Command matching must use the persisted normalized command identity from the audit event. Agent response text must never satisfy a command criterion.

- [ ] **Step 2: Run evaluator tests and verify failure**

Run: `cd backend && python -m pytest tests/test_evaluators.py -q`  
Expected: FAIL because `harness.evaluators` does not exist.

- [ ] **Step 3: Implement path and command normalization**

Path normalization returns repository-relative POSIX paths and rejects drives, leading slashes, NUL, and `..`. Command evidence exposes only the normalized command identifier, exit code, and event ID to evaluators; summaries do not echo the full raw command.

- [ ] **Step 4: Implement evaluator functions**

Every result includes evaluator version `1`, criterion ID, expected/actual summaries, and evidence references. Missing required evidence has severity `blocking`; optional missing evidence has `warning`.

- [ ] **Step 5: Run evaluator and redaction tests**

Run: `cd backend && python -m pytest tests/test_evaluators.py tests/test_audit_redaction.py tests/test_audit_risk.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/harness/evaluators.py backend/tests/test_evaluators.py
git commit -m "feat: add deterministic harness evaluators"
```

### Task 4: Orchestrate evaluation, review, and receipt advancement

**Files:**
- Modify: `backend/services/harness_service.py`
- Modify: `backend/harness/repository.py`
- Modify: `backend/api/routes.py`
- Modify: `backend/tests/test_harness_api.py`
- Create: `backend/tests/test_evaluation_service.py`

**Interfaces:**
- Produces: `HarnessService.evaluate_run(task_id: str, run_id: str) -> dict[str, Any]`
- Produces: `HarnessService.record_review(task_id: str, run_id: str, payload: dict[str, Any]) -> dict[str, Any]`
- Adds: `POST /harness/tasks/{task_id}/runs/{run_id}/evaluate`
- Adds: `GET /harness/tasks/{task_id}/runs/{run_id}/evaluations`
- Adds: `POST /harness/tasks/{task_id}/runs/{run_id}/review`

- [ ] **Step 1: Write failing service and route tests**

Assert evaluation rejects a running Run, persists deterministic results for a completed/blocked Run, and moves the Task to `needs_review`. Assert no evaluator can set `accepted`.

- [ ] **Step 2: Run tests and verify failure**

Run: `cd backend && python -m pytest tests/test_evaluation_service.py tests/test_harness_api.py -q`  
Expected: FAIL because evaluation endpoints do not exist.

- [ ] **Step 3: Implement evidence query and aggregation**

Query the bound snapshot, changed-file evidence, command-result events, and current Run. Persist results in one repository transaction where practical. Any blocking failure keeps the Task in `needs_review`.

- [ ] **Step 4: Implement human decision and receipt rules**

`accepted` requires all required machine-verifiable criteria to pass and all manual criteria to be referenced by the decision. `needs_fix` and `blocked` remain valid with failures. Advance `acknowledged → evidenced` only when each required criterion has at least one persisted evidence reference, regardless of pass/fail. Do not advance to `effective` in this task.

- [ ] **Step 5: Run API, service, and receipt tests**

Run: `cd backend && python -m pytest tests/test_evaluation_service.py tests/test_harness_api.py tests/test_context_receipts.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/services/harness_service.py backend/harness/repository.py backend/api/routes.py backend/tests/test_evaluation_service.py backend/tests/test_harness_api.py
git commit -m "feat: evaluate runs and record human decisions"
```

### Task 5: Render criteria, evidence, and review decisions

**Files:**
- Modify: `src/app/lib/harness-types.ts`
- Modify: `src/app/lib/harness-api.ts`
- Modify: `src/app/components/TaskOverview.tsx`
- Create: `src/app/components/EvaluationPanel.tsx`
- Create: `src/app/components/ReviewDecisionPanel.tsx`
- Modify: `src/app/page.tsx`

**Interfaces:**
- Produces: TypeScript `AcceptanceCriterion`, `EvaluationResult`, and `ReviewDecision`
- Produces: `evaluateRun(taskId, runId)`, `listEvaluations(taskId, runId)`, `recordReview(taskId, runId, payload)`

- [ ] **Step 1: Add exact frontend domain types and API functions**

Mirror backend string unions exactly. Keep `acceptance_criteria: Array<string | AcceptanceCriterion>` for legacy tasks.

- [ ] **Step 2: Implement criterion and evaluation rendering**

Show criterion description, required/optional label, status, blocking reason, and evidence-reference IDs. Legacy string criteria remain readable and are labeled “legacy/manual review”.

- [ ] **Step 3: Implement explicit review controls**

Require confirmation and a non-empty note. Send the ordered evaluation IDs currently shown. Disable acceptance while a blocking result exists or required evidence is absent.

- [ ] **Step 4: Run frontend gates**

Run: `npm run lint`  
Expected: PASS.

Run: `npm run build`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/app/lib/harness-types.ts src/app/lib/harness-api.ts src/app/components/TaskOverview.tsx src/app/components/EvaluationPanel.tsx src/app/components/ReviewDecisionPanel.tsx src/app/page.tsx
git commit -m "feat: add evidence evaluation workbench"
```

### Task 6: Prove the two-attempt comparison and document current status

**Files:**
- Create: `backend/tests/fixtures/acceptance_contract_v2.json`
- Create: `backend/tests/fixtures/evaluation_missing_verification.json`
- Create: `backend/tests/fixtures/evaluation_verified.json`
- Create: `backend/tests/test_evaluation_replay.py`
- Modify: `docs/context-evidence-demo.md`
- Modify: `docs/demo.md`
- Modify: `README.md`
- Modify: `DESIGN.md`
- Modify: `AGENTS.md`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Proves: attempt one `needs_fix`, attempt two eligible for `accepted`
- Documents: M0.4 vertical slice implemented; generalized M0.5 remains planned

- [ ] **Step 1: Add synthetic before/after fixtures**

Attempt one contains a bound Run and changed-file evidence but omits one required test command. Attempt two uses the same criteria and includes successful command-result evidence. All identifiers use `example-*`; all paths are relative.

- [ ] **Step 2: Write the failing replay test**

The test imports the v2 task, evaluates attempt one, records `needs_fix`, evaluates attempt two, records `accepted`, and verifies that only the reviewed comparison can advance the receipt from `evidenced` to `effective`.

- [ ] **Step 3: Implement the minimal reviewed comparison**

Add a repository/service operation that accepts the original and corrected Run IDs, verifies identical criterion IDs/config digests, verifies the first decision is `needs_fix` and second is `accepted`, then advances the receipt one level. Reject unrelated tasks or changed criterion sets.

- [ ] **Step 4: Run replay and privacy tests**

Run: `cd backend && python -m pytest tests/test_evaluation_replay.py tests/test_task_context_replay.py -q`  
Expected: PASS.

Run: `rg -n "(Bearer |sk-[A-Za-z0-9]|[A-Z]:\\\\Users\\\\|/Users/|/home/|sorenjing|小红书|腾讯)" backend/tests/fixtures docs/context-evidence-demo.md docs/demo.md`  
Expected: no matches.

- [ ] **Step 5: Update status documentation**

Mark Task/Context and this M0.4 slice implemented. Keep generalized Regression Harness and LLM Judge explicitly planned. Correct the stale AGENTS current-implementation list.

- [ ] **Step 6: Run the full quality gate**

Run: `cd backend && python -m pytest -q`  
Expected: PASS.

Run: `npm run lint`  
Expected: PASS.

Run: `npm run build`  
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/tests/fixtures backend/tests/test_evaluation_replay.py docs/context-evidence-demo.md docs/demo.md README.md DESIGN.md AGENTS.md CHANGELOG.md
git commit -m "test: prove evidence evaluation regression loop"
```
