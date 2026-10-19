import assert from "node:assert/strict";
import test from "node:test";
import { reviewRun } from "./review-selection.ts";

const first = { task_id: "task-a", run_id: "run-a", session_id: "session-a", status: "completed" };
const second = { task_id: "task-a", run_id: "run-b", session_id: "session-b", status: "blocked" };
const task = { task_id: "task-a", runs: [first, second] };

test("review targets the selected session even when another completed run comes first", () => {
  assert.equal(reviewRun(task, "session-b"), second);
  assert.equal(reviewRun(task, "session-a"), first);
});

test("unselected, unrelated and in-progress sessions cannot inherit another run's review", () => {
  for (const id of [null, "unbound-session", "session-running"]) {
    assert.equal(reviewRun({ ...task, runs: [...task.runs, { ...first, session_id: "session-running", status: "running" }] }, id), null);
  }
  assert.equal(reviewRun(null, "session-a"), null);
  assert.equal(reviewRun({ task_id: "task-b", runs: [first] }, "session-a"), null);
});
