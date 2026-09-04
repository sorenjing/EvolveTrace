# Safety Sentinel and Browser-First Launch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent a small set of destructive local Codex Bash operations before execution and make the local review workbench practical to open from a Codex session.

**Architecture:** Add a plugin-local policy module invoked by the existing collector before it sends a `PreToolUse` audit event. The collector emits Codex's documented deny shape when required, while the backend derives an extra `safety_block` finding from the persisted decision. Improve the root launcher and plugin prompts so one command starts the dashboard and a Codex built-in-browser task can open its URL.

**Tech Stack:** Python 3, FastAPI audit backend, Codex Hooks, PowerShell, Next.js.

**Spec:** `docs/superpowers/specs/2026-09-04-safety-sentinel-browser-launch-design.md`

## Global Constraints

- Preserve `/api/audit/*` event compatibility and loopback-only transport.
- Keep all policy decisions local and deterministic.
- Never persist raw Hook payloads or expose live-looking secrets.
- Do not add an agent runtime, additional LLM, cloud service, or desktop shell.
- Do not execute services, hooks, tests, lint, or builds on the current work computer.

---

### Task 1: Add test-first Safety Sentinel coverage

**Files:**
- Modify: `backend/tests/test_hook_capture.py`
- Modify: `backend/tests/test_audit_risk.py`

**Interfaces:**
- Consumes: `capture_event.process_payload(payload) -> int`
- Produces: expected Codex denial JSON and `safety_block` audit findings.

- [ ] Add assertions that disk format, raw disk write, destructive root/parent deletion, and remote-shell pipeline inputs return a denial payload.
- [ ] Add assertions that a normal project cleanup command is allowed and remains auditable.
- [ ] Add an audit risk assertion for a persisted `safety.decision = deny` record.
- [ ] Do not run the tests on the work computer.

### Task 2: Implement plugin-local pre-execution policy

**Files:**
- Create: `plugin/hooks/safety_policy.py`
- Modify: `plugin/hooks/capture_event.py`
- Modify: `backend/audit/risk.py`

**Interfaces:**
- `evaluate_pre_tool_use(payload: dict[str, Any]) -> SafetyDecision`
- `apply_safety_decision(payload: dict[str, Any], decision: SafetyDecision) -> dict[str, Any]`
- `codex_hook_output(decision: SafetyDecision) -> str | None`
- `process_payload(payload: dict[str, Any]) -> int`

- [ ] Implement the four high-confidence deny rules and fixed safe explanations.
- [ ] Persist decision metadata through the existing collector even when a denial is returned.
- [ ] Emit Codex's `hookSpecificOutput.permissionDecision = deny` shape on stdout.
- [ ] Add deterministic `safety_block` risk evidence.

### Task 3: Make launch browser-first

**Files:**
- Modify: `start.ps1`
- Modify: `plugin/.codex-plugin/plugin.json`
- Modify: `README.md`
- Modify: `plugin/README.md`
- Modify: `docs/usage.md`
- Modify: `docs/positioning.md`

**Interfaces:**
- `./start.ps1` starts both services, waits for `http://127.0.0.1:8001/api/audit/health` and `http://127.0.0.1:3000`, then opens the dashboard.
- `./start.ps1 -NoBrowser` prints the URL without launching a system browser.

- [ ] Add the launcher parameter and readiness polling.
- [ ] Update plugin prompts to request that Codex start EvolveTrace and open its dashboard in `@Browser` when that capability is available.
- [ ] Document the built-in-browser workflow and regular-browser fallback.
- [ ] Do not run the launcher on the work computer.

### Task 4: Review remote changes without execution

**Files:**
- Review all files in Tasks 1-3.

- [ ] Re-fetch every changed file from GitHub.
- [ ] Check that the hook JSON, Python imports, and user-facing claims agree with the official Codex Hook and Browser contracts.
- [ ] Report the exact commands reserved for later personal-machine verification.
