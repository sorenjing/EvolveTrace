import type { AuditEvent } from "./audit-types";

export interface AuditStep {
  id: string;
  event: AuditEvent;
  start?: AuditEvent;
  completion?: AuditEvent;
  input?: unknown;
  output?: unknown;
}

export function buildAuditSteps(events: AuditEvent[]): AuditStep[] {
  const steps: AuditStep[] = [];
  const calls = new Map<string, AuditStep>();
  const seen = new Set<string>();
  const ordered = [...events].sort((a, b) => a.sequence - b.sequence || a.timestamp.localeCompare(b.timestamp));
  for (const event of ordered) {
    if (seen.has(event.event_id)) continue;
    seen.add(event.event_id);
    const toolId = typeof event.details.tool_use_id === "string" ? event.details.tool_use_id : "";
    const key = toolId ? JSON.stringify([event.session_id, toolId]) : "";
    const isStart = event.event_type === "PreToolUse";
    const isCompletion = event.event_type === "PostToolUse" || event.event_type === "PostToolUseFailure";
    const existing = key ? calls.get(key) : undefined;
    // Different event IDs for the same phase retain their own evidence and risks.
    if ((isStart || isCompletion) && existing && !(isCompletion && existing.completion) && !(isStart && existing.start)) {
      const step = existing;
      if (isStart) step.start = event;
      if (isCompletion) {
        step.completion = event;
        step.event = event;
        if (Object.hasOwn(event.details, "tool_response")) step.output = event.details.tool_response;
      }
      if (step.input === undefined && Object.hasOwn(event.details, "tool_input")) step.input = event.details.tool_input;
      continue;
    }
    const step: AuditStep = {
      id: event.event_id,
      event,
      ...(isStart ? { start: event } : {}),
      ...(isCompletion ? { completion: event } : {}),
      ...(Object.hasOwn(event.details, "tool_input") ? { input: event.details.tool_input } : {}),
      ...(Object.hasOwn(event.details, "tool_response") ? { output: event.details.tool_response } : {}),
    };
    steps.push(step);
    if ((isStart || isCompletion) && key) calls.set(key, step);
  }
  return steps;
}

export function formatEvidence(value: unknown): string {
  if (value === undefined) return "未采集到";
  if (value === null || value === "") return "（空内容）";
  if (typeof value === "string") return value;
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}
