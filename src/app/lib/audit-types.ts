export type RiskSeverity = "high" | "medium" | "low";

export interface RiskFinding {
  event_id: string;
  code: string;
  severity: RiskSeverity;
  message: string;
  evidence?: string;
}

export interface AuditEvent {
  event_id: string;
  session_id: string;
  event_type: string;
  timestamp: string;
  turn_id: string;
  sequence: number;
  cwd: string;
  tool_name: string;
  details: Record<string, unknown>;
  risk_findings: RiskFinding[];
}

export interface AuditSessionSummary {
  session_id: string;
  cwd: string;
  started_at: string;
  last_seen: string;
  event_count: number;
  tool_call_count: number;
  modified_file_count: number;
  risk_count: number;
}

export interface AuditSession extends AuditSessionSummary {
  events: AuditEvent[];
}

export interface AuditStreamMessage {
  event: AuditEvent;
  risk_findings: RiskFinding[];
}
