export type TaskStatus = "draft" | "ready" | "active" | "evaluating" | "needs_review" | "needs_fix" | "accepted";
export type Freshness = "current" | "stale" | "missing" | "unknown";

export interface TaskContract {
  task_id: string; title: string; goal: string; target_repositories: string[];
  constraints: string[]; acceptance_criteria: string[]; open_questions: string[];
  risk_level: "normal" | "high" | "destructive"; context_snapshot_id: string | null;
  status: TaskStatus; created_at: string;
  context_snapshot?: ContextSnapshot | null; runs?: Run[];
}

export interface ContextSnapshot { snapshot_id: string; freshness: Freshness; project: string; generated_at: string; content_digest: string; }
export interface Run { run_id: string; task_id: string; context_snapshot_id: string; session_id: string | null; cwd: string; status: string; started_at: string; }
export interface UnboundRun { session_id: string; cwd: string; first_seen: string; }
