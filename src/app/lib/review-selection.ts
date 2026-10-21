import type { Run, TaskContract } from "./harness-types";

export function reviewRun(task: TaskContract | null, sessionId: string | null): Run | null {
  if (!task || !sessionId) return null;
  const run = task.runs?.find(item => item.task_id === task.task_id && item.session_id === sessionId);
  return run && (run.status === "completed" || run.status === "blocked") ? run : null;
}
