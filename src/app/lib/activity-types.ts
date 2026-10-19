export type ActivityCategory = "read_search" | "edit" | "build_test" | "dependencies" | "git" | "network" | "mixed" | "other";
export type ActivityCode = "repeated_read" | "repeated_build" | "failed_retry";

export interface ActivityFinding {
  finding_id: string;
  session_id: string;
  code: ActivityCode;
  count: number;
  window_seconds: number;
  evidence_refs: string[];
  rule_version: string;
  suppressed: boolean;
}

export interface ActivitySummary {
    attempt_count: number;
    unpaired_event_count: number;
    orphan_completion_count: number;
    denied_count: number;
    categories: Record<ActivityCategory, number>;
    failed_count: number;
    success_count: number;
    cancelled_count: number;
    result_sample_count: number;
    result_sources: { hook: number; execution_record: number; unknown: number; conflict: number };
    duration_sources: { hook: number; execution_record: number; unknown: number };
    pending_count: number;
    unknown_outcome_count: number;
    reported_duration_ms: number;
    duration_sample_count: number;
    findings: ActivityFinding[];
}

export interface ActivityProject {
  project_id: string;
  workspace_id: string;
  name: string;
  relative_path: string;
  active: boolean;
  session_count: number;
  activity: ActivitySummary & { muted_rules: ActivityCode[] };
}

export interface CaptureStatus {
  schema_version: "activity-status/v1";
  capture_state: "awaiting_events" | "receiving" | "quiet";
  started_at: string;
  last_received_at: string | null;
  received_event_count: number;
  persisted_event_count: number;
  stored_event_count: number;
  registered_project_count: number;
  observed_phases: string[];
  evidence_worker?: {
    state: "stopped" | "running" | "error";
    attempted: number;
    resolved: number;
    pending: number | null;
    last_completed_at: string | null;
    last_error: string | null;
  };
}

export interface ActivityReport {
  schema_version: "workspace-activity/v1";
  projects: ActivityProject[];
  overall_activity: ActivitySummary;
  attribution_sources: { hook_cwd: number; tool_workdir: number; execution_record: number };
  execution_metadata_scan: { files_read: number; file_limit: number; tail_byte_limit: number; limited: boolean };
  observed_event_count: number;
  unattributed_event_count: number;
  truncated: boolean;
  event_limit: number;
}

export interface AuditMemoryEntry {
  memory_id: string;
  session_id: string;
  note: string;
  evidence_refs: string[];
  created_at: string;
  status: "human_reviewed";
}

export interface AuditMemory {
  schema_version: "audit-memory/v1";
  entries: AuditMemoryEntry[];
  freshness: "historical";
  recalls?: AuditMemoryRecall[];
}

export interface AuditMemoryRecall {
  schema_version: "audit-memory-recall/v1";
  recall_id: string;
  reported_at: string;
  received_at: string;
  trigger: string;
  context_status: "returned" | "partial" | "blocked";
  context_freshness: "current" | "stale" | "new" | "unknown" | "missing";
  memory_ids: string[];
  truncated: boolean;
  authority: "client_reported_output";
  model_use: "unknown";
}
