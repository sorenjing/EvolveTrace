# Safety Sentinel and Browser-First Launch Design

## Goal

Extend EvolveTrace from passive audit to a local, deterministic pre-execution guard for high-confidence destructive commands, and reduce review friction through one launcher plus a Codex built-in-browser workflow.

## Product boundary

EvolveTrace remains local-first. It does not run an agent, inspect hidden reasoning, upload source code, or rely on an additional LLM. The guard evaluates only Hook input exposed by Codex. It is a useful guardrail rather than a complete enforcement boundary because some specialized tool paths may not use local hooks.

## Safety Sentinel

The existing `PreToolUse` hook already captures evidence but always exits successfully. The hook collector will instead:

1. Evaluate only `PreToolUse` calls whose `tool_name` is `Bash`.
2. Block only high-confidence command categories:
   - formatting or erasing a disk;
   - raw writes to a physical device;
   - recursive deletion targeting filesystem roots, home directories, or parent directories;
   - downloading arbitrary network content directly into a shell interpreter.
3. Attach a redacted `safety` decision record to the audit payload before posting it locally.
4. Emit Codex's documented `PreToolUse` denial JSON for a block, even when the audit backend is unavailable.
5. Leave ordinary project cleanup and Git recovery commands observable but not automatically blocked in this version.

The policy returns stable rule identifiers and fixed explanations; it never includes raw command text in its denial message.

## Audit evidence

The backend keeps the existing `/api/audit/*` contract. When an event contains a denied safety decision, deterministic risk analysis adds a high-severity `safety_block` finding. This makes the timeline show both the attempted command evidence and the fact that EvolveTrace prevented it.

## Browser-first workflow

The dashboard continues to be a local web UI. Codex plugins do not have a documented API for automatically embedding a persistent arbitrary dashboard pane. In the ChatGPT desktop app, however, Codex can open a localhost URL in the shared built-in browser; Codex CLI and other environments can use the same URL in a regular browser.

The launcher will therefore provide a single root entry point that starts both services, waits until each responds, prints the dashboard URL, and opens the system browser by default. Its `-NoBrowser` option supports a Codex task or user opening the printed URL through `@Browser`, which is the browser-first path. Plugin prompts and usage docs will make this first-class rather than an undocumented trick.

## Non-goals

- No sandbox, filesystem snapshotting, cloud sync, team policy service, or command allowlist UI.
- No generic `ask` decision: Codex currently does not support `ask` for `PreToolUse`.
- No claim that every destructive action can be intercepted.

## Validation plan

Tests will cover each blocking category, safe commands, audit evidence, emitted denial JSON, and launcher documentation/configuration. Per the current user constraint, this change will not run services, hooks, tests, lint, or builds on the work computer; local verification will happen later on the user's personal machine.
