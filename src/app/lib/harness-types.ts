export type TaskStatus = "draft" | "ready" | "active" | "evaluating" | "needs_review" | "needs_fix" | "accepted" | "blocked";
export type Freshness = "current" | "stale" | "missing" | "unknown";
export type ContextDeliveryStatus = "generated" | "delivered" | "acknowledged" | "evidenced" | "effective";
export type EvaluationStatus = "passed" | "failed" | "needs_review" | "skipped";
export interface AcceptanceCriterion { criterion_id: string; type: "command_exit_zero" | "path_scope" | "file_exists" | "manual"; required: boolean; description: string; config: Record<string, unknown>; }
export interface EvaluationResult { evaluation_id: string; task_id: string; run_id: string; criterion_id: string; evaluator_id: string; evaluator_version: string; status: EvaluationStatus; severity: "info" | "warning" | "blocking"; summary: string; evidence_refs: string[]; expected: string; actual: string; created_at: string; reason?: string; }
export interface ReviewDecision { decision_id: string; task_id: string; run_id: string; outcome: "accepted" | "needs_fix" | "blocked"; note: string; evaluation_ids: string[]; actor: string; created_at: string; }

export interface TaskContract {
  task_id: string; title: string; goal: string; target_repositories: string[];
  constraints: string[]; acceptance_criteria: Array<string | AcceptanceCriterion>; open_questions: string[];
  risk_level: "normal" | "high" | "destructive"; context_snapshot_id: string | null;
  status: TaskStatus; created_at: string;
  context_snapshot?: ContextSnapshot | null; runs?: Run[]; context_receipts?: ContextReceipt[]; run_comparisons?: RunComparison[];
}

export interface ContextSnapshot { snapshot_id: string; freshness: Freshness; project: string; generated_at: string; content_digest: string; }
export interface Run { run_id: string; task_id: string; context_snapshot_id: string; session_id: string | null; cwd: string; status: string; started_at: string; review_decision?: ReviewDecision | null; }
export interface RunComparison { task_id: string; original_run_id: string; corrected_run_id: string; status: "effective"; receipt_id: string; comparison_kind?: "repair"; context_benefit?: "unmeasured"; }
export interface UnboundRun { session_id: string; cwd: string; first_seen: string; }
export interface ContextReceipt {
  receipt_id: string; task_id: string; context_snapshot_id: string; attempt_id: string;
  bundle_id: string; platform: string; adapter: string; status: ContextDeliveryStatus;
  delivered_source_ids: string[]; loaded_skill_ids: string[]; created_at: string; updated_at: string;
}
