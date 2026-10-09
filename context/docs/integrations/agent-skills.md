# Runtime composition with Agent Skills

AI coding environments commonly combine three independent inputs:

| Layer | Responsibility |
|---|---|
| Project rules | Repository-specific constraints, contribution guidance, commands, architecture, and ownership. These commonly live in `AGENTS.md`, `CONTRIBUTING.md`, or equivalent files. |
| AI Context Kit | Shared workspace context: project discovery, deterministic observations, input-change detection, semantic memory, and thin adapters for coding tools. |
| Agent Skills | Reusable behaviors and workflows that apply across projects, such as review procedures, release checks, or safety practices. |

At runtime, the coding agent combines these layers with the task prompt:

```text
task prompt + project rules + shared context + reusable skills
  -> coding agent
```

AI Context Kit owns neither repository policy nor reusable behavior. Repository files remain authoritative; the context layer makes a bounded set of project observations and selected semantic memory available through one shared entry point.

## Composition, not a dependency

Agent Skills are optional. AI Context Kit has no dependency on a particular Skill repository, Skill manager, remote service, or personal configuration. It remains useful with project rules alone and can coexist with any compatible skill-discovery mechanism.

Likewise, Agent Skills should not duplicate the context store. A Skill can instruct an agent to read workspace context and run `aictx` when relevant, while AI Context Kit continues to own discovery, observed-input fingerprints, and managed context files.

This is runtime composition, not agent orchestration. Sharing context across tools does not by itself coordinate parallel agents, assign tasks, resolve concurrent edits, or merge their results.

## Framework boundary

Core discovery, freshness, and semantic memory remain framework-independent and
offline-first. A framework such as LangChain may consume a versioned
ContextBundle through a replaceable adapter, but its memory APIs do not own the
`.ai/` store or define the core context contract.

## Authority and freshness

The layers have different authority:

1. Current repository files and explicit project rules govern the work.
2. Generated observations summarize a bounded set of inputs and can be regenerated.
3. Manual semantic memory preserves decisions and constraints that deterministic scanning cannot infer.
4. Reusable Skills guide behavior but do not grant repository or system permissions.

`aictx status` calls a project `current` when its observed inputs match the inputs used for the latest render. It calls a project `stale` when those inputs changed, `new` when no recorded render exists, and `missing` when a recorded project is no longer discovered. These labels do not certify the full source tree or business behavior.

## Recommended workflow

1. Start from the current task and the repository's own instructions.
2. Read the shared workspace index and only the selected project's memory; run `aictx status` when observed inputs may have changed.
3. Apply any relevant reusable skill for the task's workflow or risk profile.
4. Inspect the source needed for the task, then make and verify the project change according to repository rules.
5. Refresh shared context only when project facts became stale, and record concise semantic decisions in the managed manual block when needed.

This keeps project constraints close to the code, shared facts in one workspace-level context store, and reusable behavior portable across repositories and agents.
