# Structured Acceptance Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make structured repository scope, constraints, and acceptance criteria durable AI Context Kit task artifacts and transport them unchanged to EvolveTrace while preserving v1 compatibility.

**Architecture:** Add immutable v2 contract value objects in `task_contracts.py`, parse a reviewed JSON contract file at the CLI boundary, and keep `task_workspace.py` responsible only for atomic artifact creation. The EvolveTrace client selects legacy or structured payloads by envelope schema and never invents v2 criteria.

**Tech Stack:** Python 3.11+, dataclasses, argparse, urllib, pytest

**Spec:** `docs/superpowers/specs/2026-09-17-structured-acceptance-contract-design.md`

## Global Constraints

- Preserve readable and submit-able `task-envelope/v1` artifacts.
- New structured tasks use exactly `task-envelope/v2`.
- Supported criterion types are `command_exit_zero`, `path_scope`, `file_exists`, and `manual`.
- Reject unknown fields, duplicate criterion IDs, absolute paths, and `..` traversal.
- Never execute criterion commands in AI Context Kit.
- Keep task directory creation atomic and workspace-locked.
- Do not add secrets, prompts, source bodies, or local absolute paths to portable artifacts.
- EvolveTrace unavailability remains fail-open; schema rejection remains explicit.

---

### Task 1: Define and validate the v2 contract

**Files:**
- Modify: `src/ai_context_kit/task_contracts.py`
- Modify: `tests/test_task_contracts.py`

**Interfaces:**
- Produces: `AcceptanceCriterion.from_dict(payload: Mapping[str, Any]) -> AcceptanceCriterion`
- Produces: `TaskEnvelopeV2.create(..., target_repositories, constraints, acceptance_criteria) -> TaskEnvelopeV2`
- Produces: `task_envelope_from_dict(payload: Mapping[str, Any]) -> TaskEnvelope | TaskEnvelopeV2`

- [ ] **Step 1: Write failing tests for valid v2 serialization**

Add a test constructing:

```python
criterion = AcceptanceCriterion.from_dict({
    "criterion_id": "backend-tests",
    "type": "command_exit_zero",
    "required": True,
    "description": "Backend tests pass",
    "config": {"command": "python -m pytest -q"},
})
envelope = TaskEnvelopeV2.create(
    task_id="task-2",
    target_project="ai-context-kit",
    target_repositories=("ai-context-kit", "EvolveTrace"),
    intent="Evolve the acceptance contract",
    requested_by="human",
    platform="codex",
    constraints=("Only modify protocol and tests",),
    acceptance_criteria=(criterion,),
    created_at=datetime(2026, 9, 17, tzinfo=timezone.utc),
)
assert envelope.to_dict()["schema"] == "task-envelope/v2"
assert envelope.to_dict()["acceptance_criteria"][0]["criterion_id"] == "backend-tests"
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest tests/test_task_contracts.py -q`  
Expected: FAIL because `AcceptanceCriterion` and `TaskEnvelopeV2` do not exist.

- [ ] **Step 3: Implement immutable criterion and v2 envelope types**

Use frozen dataclasses. Validate per-type config keys:

```python
CRITERION_CONFIG_KEYS = {
    "command_exit_zero": frozenset({"command"}),
    "path_scope": frozenset({"allowed_prefixes"}),
    "file_exists": frozenset({"path"}),
    "manual": frozenset(),
}
```

Normalize repository-relative paths with `PurePosixPath`; reject `path.is_absolute()`, drive-qualified Windows paths, empty components, and any `..` component. Limit identifiers to 100 characters and human text to 500 characters.

- [ ] **Step 4: Add failing negative tests**

Cover duplicate IDs, unknown criterion type, unknown config key, `/tmp/file`, `C:\\temp\\file`, `../secret`, empty repository lists, and unknown envelope schemas.

- [ ] **Step 5: Implement `task_envelope_from_dict` and make all focused tests pass**

The loader must construct the existing `TaskEnvelope` for v1 and `TaskEnvelopeV2` for v2; it must reject extra top-level keys rather than passing them blindly to dataclass constructors.

Run: `python -m pytest tests/test_task_contracts.py -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_context_kit/task_contracts.py tests/test_task_contracts.py
git commit -m "feat: add structured task acceptance contract"
```

### Task 2: Prepare v2 task artifacts from a reviewed contract file

**Files:**
- Modify: `src/ai_context_kit/cli.py`
- Modify: `src/ai_context_kit/task_workspace.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_task_workspace.py`
- Create: `tests/fixtures/task_contract_v2.json`

**Interfaces:**
- Consumes: `TaskEnvelopeV2`, `AcceptanceCriterion`
- Produces: `load_task_contract_file(path: Path) -> dict[str, object]`
- Changes: `prepare_task(..., contract: Mapping[str, Any] | None = None) -> PreparedTask`

- [ ] **Step 1: Add a synthetic v2 fixture and failing CLI test**

The fixture targets `projects/ai-context-kit` and `projects/EvolveTrace`, includes one `path_scope`, two `command_exit_zero`, and one `manual` criterion. The test runs:

```python
result = main([
    "task", "prepare", "demo",
    "--intent", "Evolve the contract",
    "--platform", "codex",
    "--contract", str(contract_path),
    "--workspace", str(tmp_path),
])
assert result == 0
assert json.loads(envelope_path.read_text())["schema"] == "task-envelope/v2"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_cli.py tests/test_task_workspace.py -q`  
Expected: FAIL because `--contract` is unknown.

- [ ] **Step 3: Add `--contract Path` and atomic v2 preparation**

Parse and validate the complete JSON before entering `workspace_write_lock`. Pass validated repositories, constraints, and criteria to `prepare_task`. Preserve existing no-`--contract` behavior as v1.

The generated `handoff.md` must list Task ID, Bundle ID, target repositories, and criterion IDs, without copying command bodies or context bodies.

- [ ] **Step 4: Test failure atomicity**

Add a test with an invalid path criterion and assert that `.ai/tasks/<task-id>` does not exist after failure. Add a test that duplicate task IDs still fail without modifying the existing directory.

- [ ] **Step 5: Run focused and full tests**

Run: `python -m pytest tests/test_cli.py tests/test_task_workspace.py -q`  
Expected: PASS.

Run: `python -m pytest -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_context_kit/cli.py src/ai_context_kit/task_workspace.py tests/test_cli.py tests/test_task_workspace.py tests/fixtures/task_contract_v2.json
git commit -m "feat: prepare tasks from structured contracts"
```

### Task 3: Transport v2 contracts without inventing criteria

**Files:**
- Modify: `src/ai_context_kit/evolvetrace_client.py`
- Modify: `src/ai_context_kit/cli.py`
- Modify: `tests/test_evolvetrace_client.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `TaskEnvelope | TaskEnvelopeV2`
- Produces: `build_task_payload(envelope, snapshot_id: str, repository_paths: Sequence[str]) -> dict[str, Any]`

- [ ] **Step 1: Write failing payload tests for v1 and v2**

Assert v1 retains the current legacy strings. Assert v2 sends exact structured constraints and criteria from the artifact:

```python
assert task_payload["acceptance_criteria"] == envelope.to_dict()["acceptance_criteria"]
assert task_payload["target_repositories"] == ["projects/ai-context-kit", "projects/EvolveTrace"]
```

- [ ] **Step 2: Run the client tests and verify failure**

Run: `python -m pytest tests/test_evolvetrace_client.py -q`  
Expected: FAIL because the client still hardcodes one generic criterion.

- [ ] **Step 3: Implement schema-aware payload construction**

For v2, compare the contract repositories with bundle repository identifiers and reject mismatches before the first HTTP request. Do not downgrade or synthesize criteria. Keep the existing snapshot → task → receipt → activation order.

- [ ] **Step 4: Load task artifacts through the schema-aware loader**

Replace `TaskEnvelope(**envelope_payload)` in the submit command with `task_envelope_from_dict(envelope_payload)`. Convert contract validation errors to `ConfigError` so the CLI exits with code 2 and an actionable message.

- [ ] **Step 5: Run integration-style client tests and full suite**

Run: `python -m pytest tests/test_evolvetrace_client.py tests/test_cli.py -q`  
Expected: PASS.

Run: `python -m pytest -q`  
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ai_context_kit/evolvetrace_client.py src/ai_context_kit/cli.py tests/test_evolvetrace_client.py tests/test_cli.py
git commit -m "feat: submit structured acceptance contracts"
```

### Task 4: Document and verify the producer side

**Files:**
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Create: `examples/task-contract-v2.json`

**Interfaces:**
- Documents: `aictx task prepare <project> --contract <path>`
- Documents: v1 compatibility and EvolveTrace consumer requirement

- [ ] **Step 1: Add a public-safe example contract**

Use synthetic repositories `projects/example-api` and `projects/example-ui`. Commands may be `python -m pytest -q` and `npm test`; paths must be relative.

- [ ] **Step 2: Update README task workflow**

Explain that AI Context Kit validates and transports criteria but does not execute them or claim success. Show prepare and submit commands and the v1 fallback.

- [ ] **Step 3: Run documentation and privacy checks**

Run: `python -m pytest tests/test_skill.py tests/test_cli.py -q`  
Expected: PASS.

Run: `rg -n "(Bearer |sk-[A-Za-z0-9]|[A-Z]:\\\\Users\\\\|/Users/|/home/)" README.md CHANGELOG.md examples/task-contract-v2.json`  
Expected: no matches.

- [ ] **Step 4: Run the full quality gate**

Run: `python -m pytest -q`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md CHANGELOG.md examples/task-contract-v2.json
git commit -m "docs: explain structured acceptance tasks"
```
