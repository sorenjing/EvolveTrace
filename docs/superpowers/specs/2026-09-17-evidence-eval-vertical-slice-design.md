# Evidence Evaluation Vertical Slice Design

Date: 2026-09-17  
Status: approved design  
Companion specification: `sorenjing/ai-context-kit/docs/superpowers/specs/2026-09-17-structured-acceptance-contract-design.md`

## Purpose

EvolveTrace already stores Task Contracts, Context Snapshots, Runs, and monotonic Context Receipts through `acknowledged`. The missing link is a deterministic, evidence-referenced evaluation path from structured acceptance criteria to a human review decision.

This vertical slice implements the smallest useful part of M0.4 and proves it with a real two-repository protocol change. It does not implement the complete regression harness or an LLM judge.

## Ownership boundary

- AI Context Kit owns task preparation, context discovery, freshness rendering, structured constraints, structured acceptance criteria, and transport.
- EvolveTrace owns imported immutable snapshots, task/run binding, audit evidence, deterministic evaluation, receipt advancement, and human decisions.
- Repository files and repository test commands remain the source of truth.
- EvolveTrace does not run the Coding Agent and does not infer hidden model cognition.

## Input contract

EvolveTrace accepts both legacy Task Contracts and the new structured acceptance contract from `task-envelope/v2`.

A structured criterion contains:

- stable `criterion_id`;
- supported `type`;
- `required` flag;
- human-readable `description`;
- type-specific `config`.

Unknown fields, unknown types, duplicate identifiers, absolute paths, and path traversal are rejected. Once a Task has a bound Run, its criteria are immutable; a revised task requires a new task identity.

## First evaluators

### Context Freshness

Input: bound Context Snapshot.

- `current` passes.
- `stale`, `missing`, incompatible schema, or absent required snapshot produces a blocking failure.
- `unknown` produces `needs_review`.

### Repository Scope

Input: target repositories, allowed path prefixes, and changed-file evidence.

- Every changed path is normalized and compared against repository-relative allowed prefixes.
- Any traversal, absolute path, wrong repository, or unexpected prefix is a blocking failure.
- No changed-file evidence produces `needs_review`; absence is not treated as proof of no changes.

### Verification Evidence

Input: `command_exit_zero` criteria and observable command-result events.

- A matching normalized command with exit code zero passes.
- A matching command with nonzero exit code fails.
- No matching execution evidence produces a blocking failure for a required criterion and `needs_review` for an optional criterion.
- Agent text claiming that tests passed is not command evidence.

### File Existence and Manual Criteria

`file_exists` evaluates only inside the selected local workspace boundary and records the checked repository-relative path. It never follows a portable absolute path from the contract.

`manual` always remains `needs_review` until a human decision references it.

## Evaluation result

Each persisted result contains:

```text
evaluation_id
task_id
run_id
criterion_id
evaluator_id
evaluator_version
status: passed | failed | needs_review | skipped
severity: info | warning | blocking
summary
evidence_refs[]
expected
actual
created_at
```

Evidence references point to persisted audit events, changed-file findings, snapshots, or review records. Summaries and actual values pass through redaction and do not echo raw secrets or full dangerous commands.

Evaluation writes are idempotent for the same task, run, criterion, evaluator, and evaluator version. Re-evaluation with changed evidence creates a new evaluation attempt or versioned result rather than silently rewriting the historical conclusion.

## Aggregation and lifecycle

- A blocking failure prevents automatic acceptance and moves the Task to `needs_review`.
- Missing required evidence is never averaged away by successful optional criteria.
- Evaluators do not directly mark a Task `accepted`.
- A human records `accepted`, `needs_fix`, or `blocked`, with a note and immutable snapshot of referenced evaluation identifiers.
- A destructive Safety Sentinel block makes the Run blocked and still requires human review.

Receipt advancement remains monotonic:

- `acknowledged`: an observable Run is bound.
- `evidenced`: every required machine-verifiable criterion has persisted evidence references; this does not mean it passed.
- `effective`: a human-accepted corrected run is compared with a prior failed or needs-fix run under the same criterion set.

A single successful run cannot automatically produce `effective`.

## API and interface

Backend endpoints cover:

- listing criteria and evaluation results for a Task/Run;
- starting deterministic evaluation for a completed or blocked Run;
- recording an immutable human Review Decision;
- reading the comparison between the original and corrected attempts.

The Task-first UI adds:

- criterion status and blocking reason;
- clickable evidence references;
- context freshness and scope findings;
- human decision controls;
- a compact before/after comparison for the demonstration.

Existing audit APIs and session timelines remain compatible.

## First real two-repository demonstration

Task: evolve structured acceptance criteria across AI Context Kit and EvolveTrace while preserving v1 compatibility.

Attempt one:

1. Prepare and submit a v2 task targeting both repositories.
2. Bind a real Codex Hook Run.
3. Modify the protocol and consumer.
4. Omit one required repository test command.
5. Evaluation reports missing verification evidence.
6. Human records `needs_fix`.

Attempt two:

1. Keep the same criterion definitions and create a new execution attempt.
2. Run both repositories' required deterministic checks.
3. Scope and verification evaluators pass.
4. Human records `accepted`.
5. A comparison may advance the receipt to `effective`.

The public regression fixture is a synthetic, redacted representation of this behavior. It contains no private workspace content, real prompts, credentials, company data, personal identifiers, or local absolute paths.

## Failure handling

- Evaluation against a running Run is rejected.
- Missing or malformed evidence yields a structured result instead of an exception where possible.
- Database writes use repository transactions and preserve prior evaluation history.
- Duplicate API requests return the existing immutable result or decision when payloads match and reject conflicts.
- SSE delivery is advisory; SQLite remains the evidence source of truth.
- UI failure cannot change Task, receipt, evaluation, or decision state.

## Testing

Backend tests cover:

- structured contract validation and v1 compatibility;
- evaluator pass, fail, needs-review, and skipped outcomes;
- evidence-reference integrity;
- required evidence aggregation;
- receipt monotonicity and forbidden automatic `effective`;
- idempotent evaluation and review writes;
- scope normalization and traversal rejection;
- redaction and public-fixture privacy.

Frontend tests cover:

- criterion and blocking-state rendering;
- evidence-reference navigation;
- review decision confirmation;
- before/after comparison;
- API failure and empty-evidence states.

The repository quality gate remains backend tests, frontend lint, and frontend build. The real demonstration additionally runs AI Context Kit's test gate.

## Out of scope

- LLM judges;
- arbitrary user-authored evaluator plugins;
- automatic semantic correctness claims;
- cloud synchronization or team permissions;
- Agent execution or orchestration;
- full filesystem sandboxing;
- generalized replay of external services;
- automatic publication of private regression cases.

## Documentation consistency

Implementation must update README, DESIGN milestone status, demo instructions, API types, and AGENTS current-implementation text. M0.5 Regression Harness remains planned except for the single synthetic before/after demonstration needed to validate this slice.
