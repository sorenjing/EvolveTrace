import assert from "node:assert/strict";
import test from "node:test";
import { activityPrompt } from "./activity-prompt.ts";

test("analysis prompt cites captured evidence without a hardware diagnosis", () => {
  const prompt = activityPrompt({ name: "demo", project_id: "p-1", relative_path: "projects/demo" },
    { session_id: "s-1", code: "repeated_read", count: 5, window_seconds: 600, evidence_refs: ["e-1", "e-2"], rule_version: "activity/v1" });
  assert.match(prompt, /p-1/);
  assert.match(prompt, /s-1/);
  assert.match(prompt, /e-1, e-2/);
  assert.match(prompt, /未采集实际 I\/O/);
  assert.match(prompt, /先核对证据/);
  assert.doesNotMatch(prompt, /磁盘已经损坏/);
});
