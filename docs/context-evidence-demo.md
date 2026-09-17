# Context-to-Evidence Demonstration

This document records the public-safe result of the first context-to-evidence vertical slice. All identifiers below are synthetic examples; private repository content, prompts, local paths, credentials, and hidden reasoning are intentionally excluded.

## Demonstrated flow

```text
TaskEnvelope
  -> task-bound ContextBundle
  -> ContextReceipt generated
  -> optional submission to EvolveTrace
  -> TaskContract and ContextSnapshot bound
  -> first matching Hook creates a Run
  -> receipt advances delivered -> acknowledged
```

Example public-safe identities:

```text
task_id: task_demo_01
bundle_id: ctx_demo_01
snapshot_id: 00000000-0000-4000-8000-000000000001
receipt_id: receipt_demo_01
run_id: 00000000-0000-4000-8000-000000000002
```

## What this proves

- A task can carry stable task, bundle, source, and Skill identities without copying unrestricted source bodies.
- Receipt ingestion is idempotent and delivery states advance monotonically.
- A matching execution Hook can bind the delivered receipt to an observable Run.
- EvolveTrace can display which bounded context and behavior identifiers were delivered.
- If EvolveTrace is unavailable, the source task remains valid and the CLI reports incomplete observability.
- Deterministic repository checks and a privacy scan can be performed independently of the receipt.

## What this does not prove

- A receipt does not prove that a model read, understood, or followed the context.
- `acknowledged` does not mean `effective`.
- No controlled comparison has established that this context improved task quality.
- ChatGPT, Claude, Cursor, and Gemini adapters are not implemented by this demonstration.
- EvolveTrace is not a source of truth for project state and is not required for source correctness.

## Delivery vocabulary

| State | Meaning |
| --- | --- |
| `generated` | The receipt artifact exists locally. |
| `delivered` | The bounded identities were accepted by the evidence sink. |
| `acknowledged` | An execution attempt was observably bound to the task. |
| `evidenced` | Observable output references the governed context identities. |
| `effective` | A reviewed comparison supports an effectiveness claim. |

States never claim access to hidden model cognition.

## Privacy boundary

The demonstration exports only allowlisted identifiers and timestamps. It excludes authorization headers, cookies, tokens, raw prompts, source bodies, absolute private paths, chain-of-thought, and arbitrary metadata.

## Reproduce locally

1. Prepare a task with `aictx task prepare`.
2. Start EvolveTrace on loopback.
3. Submit the generated task with `aictx task submit <task-id> --evolvetrace-url http://127.0.0.1:8000`.
4. Run the task through the configured execution Hook.
5. Inspect the task's Context Delivery card and verify the bound receipt and Run.
6. Run the target repository's deterministic checks and privacy scan.
7. Require human review before accepting any reusable semantic lesson.

The exact commands and schemas are documented in AI Context Kit and EvolveTrace.