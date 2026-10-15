import test from "node:test";
import assert from "node:assert/strict";
import { recoverSession } from "./audit-recovery.ts";

const event = (id, sequence) => ({ event_id: id, session_id: "synthetic", sequence });
const session = events => ({ session_id: "synthetic", events, event_count: events.length });

test("snapshot recovery preserves live arrivals, deduplicates, and orders offline events", () => {
  const snapshot = session(Array.from({ length: 10 }, (_, i) => event(String(i), i)));
  const current = session([event("0", 0), event("9", 9), event("10", 10)]);
  assert.deepEqual(recoverSession(snapshot, current).events.map(e => e.event_id), Array.from({length: 11}, (_, i) => String(i)));
});

test("stale recovery never overwrites a different selected session", () => {
  const current = { session_id: "other", events: [] };
  assert.equal(recoverSession(session([event("old", 1)]), current), current);
  assert.equal(recoverSession(session([]), null), null);
});
