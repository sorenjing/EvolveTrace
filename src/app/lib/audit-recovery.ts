import type { AuditSession } from "./audit-types";

// The persisted snapshot fills an offline gap; retain events arriving while
// that request was in flight. A response for an old selection is discarded.
export function recoverSession(snapshot: AuditSession, current: AuditSession | null): AuditSession | null {
  if (current?.session_id !== snapshot.session_id) return current;
  const events = new Map(snapshot.events.map(event => [event.event_id, event]));
  for (const event of current.events) {
    if (!events.has(event.event_id)) events.set(event.event_id, event);
  }
  const ordered = [...events.values()].sort((a, b) => a.sequence - b.sequence || a.event_id.localeCompare(b.event_id));
  return { ...snapshot, events: ordered, event_count: ordered.length };
}
