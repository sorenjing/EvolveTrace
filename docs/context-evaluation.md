# Evaluate context delivery on a real task

Use the same bounded repository task twice: once with ordinary repository
inspection and once with an AI Context Kit task bundle. This is a local
evaluation procedure, not a claim of measured productivity gains. Do not use
private repository names, code, prompts, or transcript excerpts in public
fixtures.

The [ContextBundle evaluation method](context-bundle-evaluation.md) defines
the comparison measures and interpretation. The steps below describe how to
prepare and record each local attempt.

## Prepare

1. Write one concrete task and its acceptance checks before either run. List
   the authoritative files and rules that a successful worker must discover.
2. Use the same repository revision, coding tool, model, task wording, time
   budget, and checks for both runs. Use separate clean worktrees so changes
   from the first attempt cannot help the second.
3. In the bundle arm, run `aictx status` and refresh stale observations with
   `aictx update`; then run `aictx task prepare` with a reviewed v2 contract.
   Inspect `bundle.json` for `sources`, `observed_scope`, `freshness`,
   `conflicts`, and selected repositories before handing it to the worker.
4. Randomize which arm runs first if repeating the task with several workers.
   One developer repeating the same task will remember the solution, so a
   single sequential comparison is exploratory only.

## Record separately for each arm

| Field | What to record |
| --- | --- |
| Source discovery | Which predeclared authoritative files and rules were actually opened; where each came from |
| Context size | Characters or tokens delivered to the tool, using the same counting method |
| Freshness | Source revision/digest and whether a required source changed after bundle generation |
| Task outcome | The same acceptance command results and a human review of the diff |
| Time and cost | Elapsed time, model usage, and any failed tool calls if the tool exposes them |
| Errors | Missed constraints, wrong repository, stale statement, duplicate change, or unsafe disclosure |

Report the raw observations and the number of predeclared sources found in
each arm. A smaller bundle is not automatically better; a passed test does not
prove the worker used the intended source; and a `delivered` ContextReceipt
does not prove comprehension. If the bundle omitted a needed rule, inspect
whether the source was outside the allowlist, stale, incorrectly scoped, or
present but ignored. Correct the authority or selection rule at its owner,
then rerun on a new task rather than tuning against the same example.

The current bundle records source IDs and content digests only for configured
context sources plus the rendered project context. `observed_scope` describes
bounded metadata inputs; it is not a full code index. Direct inspection of
current code and tests remains necessary.
