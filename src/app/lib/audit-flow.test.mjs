import assert from "node:assert/strict";
import test from "node:test";
import { buildAuditSteps, formatEvidence } from "./audit-flow.ts";

const event = (id, type, sequence, details = {}) => ({
  event_id: id, session_id: "session", event_type: type,
  timestamp: `2026-01-01T00:00:${String(sequence).padStart(2, "0")}Z`,
  turn_id: "turn", sequence, cwd: "sample", tool_name: "Bash",
  details, risk_findings: [],
});

test("pairs tool start and completion into one chronological step", () => {
  const steps = buildAuditSteps([
    event("start", "PreToolUse", 1, { tool_use_id: "call-1", tool_input: { command: "git status" } }),
    event("other", "UserPromptSubmit", 2, { prompt: "Review changes" }),
    event("finish", "PostToolUse", 3, { tool_use_id: "call-1", tool_response: { stdout: "clean", exit_code: 0 } }),
  ]);
  assert.equal(steps.length, 2);
  assert.deepEqual(steps.map((step) => step.id), ["start", "other"]);
  assert.equal(steps[0].start?.event_id, "start");
  assert.equal(steps[0].completion?.event_id, "finish");
  assert.equal(steps[0].input.command, "git status");
  assert.equal(steps[0].output.stdout, "clean");
});

test("keeps unmatched events and distinguishes missing output from empty output", () => {
  const steps = buildAuditSteps([
    event("pending", "PreToolUse", 1, { tool_use_id: "a", tool_input: { command: "npm test" } }),
    event("orphan", "PostToolUse", 2, { tool_use_id: "b", tool_response: "" }),
  ]);
  assert.equal(steps.length, 2);
  assert.equal(steps[0].output, undefined);
  assert.equal(steps[1].output, "");
  assert.equal(formatEvidence(steps[1].output), "（空内容）");
});

test("pairs by session and call even when the optional turn is missing", () => {
  const steps = buildAuditSteps([
    { ...event("start", "PreToolUse", 1, { tool_use_id: "call" }), turn_id: "" },
    event("finish", "PostToolUse", 2, { tool_use_id: "call", tool_response: "done" }),
  ]);
  assert.equal(steps.length, 1);
  assert.equal(steps[0].completion.event_id, "finish");
});

test("never pairs the same call ID across sessions", () => {
  const steps = buildAuditSteps([
    event("start", "PreToolUse", 1, { tool_use_id: "call" }),
    { ...event("finish", "PostToolUse", 2, { tool_use_id: "call" }), session_id: "another" },
  ]);
  assert.equal(steps.length, 2);
  assert.equal(steps[0].completion, undefined);
});

test("failure completion and late start stay in one step", () => {
  const steps = buildAuditSteps([
    event("failed", "PostToolUseFailure", 1, { tool_use_id: "call", tool_response: "failed" }),
    event("late-start", "PreToolUse", 2, { tool_use_id: "call", tool_input: { command: "npm test" } }),
  ]);
  assert.equal(steps.length, 1);
  assert.equal(steps[0].event.event_id, "failed");
  assert.equal(steps[0].start.event_id, "late-start");
  assert.equal(steps[0].completion.event_id, "failed");
  assert.equal(steps[0].input.command, "npm test");
});

test("duplicate delivered events do not duplicate timeline steps", () => {
  const start = event("start", "PreToolUse", 1, { tool_use_id: "call" });
  const finish = event("finish", "PostToolUse", 2, { tool_use_id: "call" });
  const steps = buildAuditSteps([start, start, finish, finish]);
  assert.equal(steps.length, 1);
  assert.equal(steps[0].completion.event_id, "finish");
});

for (const failureFirst of [true, false]) {
  test(`preserves both terminal records and failure evidence (${failureFirst ? "failure" : "success"} first)`, () => {
    const failure = event("failure", "PostToolUseFailure", failureFirst ? 2 : 3, {
      tool_use_id: "call", tool_response: { exit_code: 1 },
    });
    failure.risk_findings = [{ event_id: "failure", code: "tool_failure", severity: "medium", message: "Synthetic failure" }];
    const success = event("success", "PostToolUse", failureFirst ? 3 : 2, {
      tool_use_id: "call", tool_response: { exit_code: 0 },
    });
    const steps = buildAuditSteps([
      event("start", "PreToolUse", 1, { tool_use_id: "call" }), failure, success,
    ]);
    assert.equal(steps.length, 2);
    assert.deepEqual(new Set(steps.map(step => step.completion.event_id)), new Set(["failure", "success"]));
    assert.deepEqual(new Set(steps.map(step => step.output.exit_code)), new Set([0, 1]));
    assert.equal(steps.flatMap(step => step.completion.risk_findings).filter(item => item.code === "tool_failure").length, 1);
  });
}

test("different start records retain their own safety evidence", () => {
  const denied = event("denied-start", "PreToolUse", 1, { tool_use_id: "call" });
  denied.risk_findings = [{ event_id: "denied-start", code: "safety_block", severity: "high", message: "Synthetic block" }];
  const steps = buildAuditSteps([
    denied,
    event("another-start", "PreToolUse", 2, { tool_use_id: "call" }),
    event("finish", "PostToolUse", 3, { tool_use_id: "call", tool_response: { exit_code: 0 } }),
  ]);
  assert.equal(steps.length, 2);
  assert.deepEqual(steps.map(step => step.start.event_id), ["denied-start", "another-start"]);
  assert.equal(steps[0].start.risk_findings[0].code, "safety_block");
});
