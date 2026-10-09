# Structured Acceptance Contract Design

Date: 2026-09-17  
Status: approved design  
Companion specification: `sorenjing/EvolveTrace/docs/superpowers/specs/2026-09-17-evidence-eval-vertical-slice-design.md`

## Purpose

AI Context Kit already creates a task-bound `TaskEnvelope`, `ContextBundle v1`, and `ContextReceipt`, then optionally submits them to EvolveTrace. The current submission client weakens that contract by generating one generic constraint and one generic acceptance sentence at submission time.

This change makes constraints and acceptance criteria part of the durable task artifact. AI Context Kit owns their authoring, validation, serialization, and transport. EvolveTrace owns execution evidence, evaluation, review decisions, and regression cases.

## Scope

The first release supports four criterion types:

- `command_exit_zero`: a named verification command must have observable successful execution evidence.
- `path_scope`: changed paths must remain inside declared repository-relative prefixes.
- `file_exists`: a repository-relative artifact must exist when evaluated.
- `manual`: a human must record the final decision.

This release does not execute commands, inspect arbitrary source code, infer semantic correctness, or advance a receipt to `effective`.

## Contract changes

### TaskEnvelope v2

A prepared task adds:

- `target_repositories`: one or more workspace-relative repository identifiers.
- `constraints`: structured, user-reviewed task constraints.
- `acceptance_criteria`: ordered structured criteria.

Each criterion contains:

```json
{
  "criterion_id": "backend-tests",
  "type": "command_exit_zero",
  "required": true,
  "description": "Backend tests complete successfully",
  "config": {
    "command": "python -m pytest -q"
  }
}
```

Criterion identifiers are unique inside one task and stable across retries. Unknown criterion types or unknown configuration keys are rejected. Commands and paths are stored as user-provided task requirements; AI Context Kit does not execute them.

### Compatibility

Existing `task-envelope/v1` artifacts remain readable and submit-able. They are translated to the existing legacy EvolveTrace payload and do not silently acquire stronger acceptance claims.

New tasks use `task-envelope/v2`. A v2 task cannot be downgraded to v1 during submission. EvolveTrace schema rejection remains an explicit error; sink unavailability remains fail-open for source work and returns incomplete observability.

### CLI

`aictx task prepare` accepts repeatable, explicit inputs for repository scope, constraints, and criteria. Complex criteria may be supplied through a reviewed JSON file to avoid fragile shell quoting. The generated task directory remains atomic and contains:

- `envelope.json`
- `bundle.json`
- `receipt.json`
- `handoff.md`

`handoff.md` summarizes identifiers and instructs the execution client to use the machine-readable contract. It does not duplicate unrestricted source content.

## Validation and privacy

- Repository and file paths must be workspace-relative and cannot contain `..` traversal.
- Portable contracts reject absolute Windows and POSIX paths.
- Criterion descriptions and constraints have bounded lengths.
- Unknown fields are rejected to prevent accidental schema drift.
- Secrets, raw prompts, source bodies, and local absolute paths are not added to task artifacts.
- The publication flow remains separate; task artifacts are local unless the user explicitly exports them.

## Submission flow

```text
aictx task prepare
  -> validate TaskEnvelope v2
  -> atomically write task artifacts
  -> aictx task submit
  -> submit ContextSnapshot
  -> submit TaskContract with structured criteria
  -> submit delivered ContextReceipt
  -> activate task lease
```

The EvolveTrace client transports the prepared contract without inventing acceptance criteria. A successful HTTP response proves delivery only.

## Failure behavior

- Invalid criteria fail before any task directory is committed.
- Existing task identifiers remain immutable.
- A partial remote submission reports a schema error or unavailable sink; it never rewrites local criteria.
- Repeated submission is idempotent when immutable identifiers and payloads match.
- Conflicting payloads for an existing task identifier are rejected by EvolveTrace.

## Testing

Tests cover:

- v2 criterion creation, ordering, uniqueness, and serialization;
- every supported criterion type and rejected unknown types;
- traversal, absolute path, empty field, oversized field, and unknown-key rejection;
- atomic task preparation when validation or writing fails;
- unchanged v1 read and submission behavior;
- exact v2 payload transport without client-generated criteria;
- loopback URL restriction and fail-open sink unavailability;
- public fixtures containing only synthetic repository names, paths, and commands.

## Demonstration task

The first real task evolves this protocol across AI Context Kit and EvolveTrace. The contract targets both repositories, limits modifications to the protocol, domain, API, tests, and documentation paths, and requires both repositories' deterministic test gates.

The first captured attempt intentionally lacks one required verification result and must remain `needs_review`. The corrected attempt supplies the missing evidence and becomes eligible for human acceptance. This comparison is the evidence required before any `effective` claim.

## Documentation consistency

Implementation must update README and task command documentation. It must also correct any current-status document that still describes Task Contracts or Context Receipts as future work. Planned evaluator and regression capabilities remain labeled as planned until their tests land.
