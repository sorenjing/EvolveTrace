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
  const pending = new Map<string, AuditStep>();
  const ordered = [...events].sort((a, b) => a.sequence - b.sequence || a.timestamp.localeCompare(b.timestamp));
  for (const event of ordered) {
    const toolId = typeof event.details.tool_use_id === "string" ? event.details.tool_use_id : "";
    const key = toolId ? `${event.turn_id}:${toolId}` : "";
    if (event.event_type === "PostToolUse" && key && pending.has(key)) {
      const step = pending.get(key)!;
      step.completion = event;
      step.event = event;
      if (step.input === undefined && Object.hasOwn(event.details, "tool_input")) step.input = event.details.tool_input;
      if (Object.hasOwn(event.details, "tool_response")) step.output = event.details.tool_response;
      pending.delete(key);
      continue;
    }
    const step: AuditStep = {
      id: event.event_id,
      event,
      ...(event.event_type === "PreToolUse" ? { start: event } : {}),
      ...(event.event_type === "PostToolUse" ? { completion: event } : {}),
      ...(Object.hasOwn(event.details, "tool_input") ? { input: event.details.tool_input } : {}),
      ...(Object.hasOwn(event.details, "tool_response") ? { output: event.details.tool_response } : {}),
    };
    steps.push(step);
    if (event.event_type === "PreToolUse" && key) pending.set(key, step);
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
