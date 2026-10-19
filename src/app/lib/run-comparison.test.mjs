import assert from "node:assert/strict";
import test from "node:test";
import { reviewedRuns, comparisonRows } from "./run-comparison.ts";

test("comparison choices require a matching saved human decision and finished run", () => {
  const run = { run_id: "before", task_id: "task", status: "completed", review_decision: { task_id: "task", run_id: "before", outcome: "needs_fix" } };
  const task = { task_id: "task", runs: [run, { ...run, status: "running" }, { ...run, run_id: "wrong" }, { ...run, review_decision: null }] };
  assert.deepEqual(reviewedRuns(task, "needs_fix"), [run]);
  assert.deepEqual(reviewedRuns(task, "accepted"), []);
});

test("comparison aligns criterion and evaluator identity and preserves missing evidence", () => {
  const before = [{ criterion_id: "tests", evaluator_id: "verification", status: "failed" }, { criterion_id: "scope", evaluator_id: "repository-scope", status: "passed" }];
  const after = [{ criterion_id: "tests", evaluator_id: "verification", status: "passed" }];
  assert.deepEqual(comparisonRows(before, after).map(row => [row.criterionId, row.before?.status, row.after?.status]), [["tests", "failed", "passed"], ["scope", "passed", undefined]]);
  assert.equal(comparisonRows(before, [{ ...after[0], evaluator_id: "different" }]).length, 3);
});
