# Cross-project audit and reviewed memory

The merged Context component supplies project discovery and scoped memory access;
the audit layer supplies command observations and evidence-linked human review.

## Contract

Context owns discovery. `aictx audit sync` submits a versioned workspace project
index to the loopback backend; the backend never imports Context internals or
parses Markdown. Workspace roots are local routing metadata, excluded from
reports and reviewed-memory exports. Project identity includes the workspace;
the longest matching registered project path owns an event. Unknown paths stay
unattributed. Registration is idempotent and can classify existing evidence.

The audit layer derives bounded statistics from sanitized stored events. Pair
Pre/Post events only with a captured tool_use_id, count a pair once, and preserve
unpaired evidence. Classify search/read, edit, build/test, dependencies, Git,
network, mixed and other. Distinct command arguments remain distinct. Report
observed failures, pending/unknown outcomes, and explicitly reported duration;
never call Hook wall time CPU or disk time. Use at most 20,000 events per report
and declare truncation. Analysis does not add work to synchronous Hooks.
Denied calls are reported separately. Missing pairing IDs are explicit coverage
gaps; pending attempts do not trigger repetition. Exact stripped command text
forms identity to preserve attached quoted arguments.

Rules v1 inspect a 600-second captured window per session: at least five repeated
read/build attempts without captured edit evidence, or three consecutive observed
failures of the same command. Findings cite event IDs, are suggestions for human
review, and do not assert lack of real edits, physical I/O, causality or disk
damage. Incomplete timestamps or redacted commands do not trigger repetition.

An EvolveTrace panel shows project statistics and findings. Analysis is opt-in:
a local dialog prepares an evidence-referencing prompt for the user to copy to
Codex. Ignore a session finding or mute a rule for a project; settings persist.
No native Codex popup API, model calls, background Agent, or hardware sensor is
claimed. Users can explicitly save a reviewed note tied to project, session and
valid evidence IDs; only these notes are reusable audit memory. Deleting a
session also removes its notes. No automatic writes to .ai semantic memory.

`aictx audit report [project]`, `aictx audit memory <project>`, and
`aictx audit remember <project> --session-id ... --event-id ... --note ...` use
the versioned HTTP contract. `aictx load <project> --audit-url ...` optionally
returns only that project's reviewed memory, separately labeled from local
context freshness; backend failure leaves normal context delivery usable.
SessionStart can opt in with `EVOLVETRACE_AUDIT_MEMORY_URL`. Delivered note IDs
are recorded as separate receipt metadata; bounded recall never stores note text
in loading receipts or promotes historical observations to current freshness.

## Validation and value

Use synthetic events and temporary workspaces for pairing, missing phases,
quoted arguments, edit interleaving, success breaking failure streaks, project
isolation, nested roots, truncation, persistence, evidence validation, redaction,
loopback enforcement and fail-open context loading. Run backend and Context
tests, frontend lint and static build, then inspect the local UI with synthetic
evidence. Existing event and ContextBundle v1 contracts remain compatible.

This is a first product experiment. Continue when findings lead to a verified
change that reduces repeated work; revise if normal edit/test loops dominate
alerts or monitoring overhead becomes visible. OS resource sampling and hardware
health remain a separate future design.
