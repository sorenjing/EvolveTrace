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
