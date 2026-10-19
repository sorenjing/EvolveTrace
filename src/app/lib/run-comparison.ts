import type { EvaluationResult, ReviewDecision, TaskContract } from "./harness-types";

export function reviewedRuns(task: TaskContract, outcome: ReviewDecision["outcome"]) {
  return (task.runs ?? []).filter(run => run.task_id === task.task_id
    && (run.status === "completed" || run.status === "blocked")
    && run.review_decision?.task_id === task.task_id && run.review_decision.run_id === run.run_id
    && run.review_decision.outcome === outcome);
}

export function comparisonRows(before: EvaluationResult[], after: EvaluationResult[]) {
  const identity = (item: EvaluationResult) => JSON.stringify([item.criterion_id, item.evaluator_id]);
  const original = new Map(before.map(item => [identity(item), item]));
  const corrected = new Map(after.map(item => [identity(item), item]));
  return [...new Set([...original.keys(), ...corrected.keys()])].map(key => ({
    key, criterionId: (original.get(key) ?? corrected.get(key))!.criterion_id,
    before: original.get(key), after: corrected.get(key),
  }));
}
