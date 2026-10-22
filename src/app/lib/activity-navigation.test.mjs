import assert from "node:assert/strict";
import test from "node:test";
import { projectForSession, activityFindings, evidenceStepId } from "./activity-navigation.ts";

const projects = [
  { project_id: "first", sessions: [{ session_id: "shared" }, { session_id: "single" }] },
  { project_id: "second", sessions: [{ session_id: "shared" }] },
];

test("session navigation keeps the chosen project for a cross-project session", () => {
  assert.equal(projectForSession(projects, "shared", "second"), "second");
});
test("an unambiguous session selects its observed project", () => {
  assert.equal(projectForSession(projects, "single", "second"), "first");
});
test("ambiguous or unattributed sessions never guess a project", () => {
  assert.equal(projectForSession(projects, "shared", null), null);
  assert.equal(projectForSession(projects, "unknown", "first"), null);
});
test("older service metadata without session membership remains unknown", () => {
  assert.equal(projectForSession([{ project_id: "first" }], "single", null), null);
});

test("overview includes project and unattributed findings without reviving ignored findings", () => {
  const ignored = { finding_id: "ignored", suppressed: true, code: "repeated_read" };
  const failed = { finding_id: "failed", suppressed: false, code: "failed_retry" };
  const unknown = { finding_id: "unknown", code: "repeated_build" };
  const project = { project_id: "first", activity: { findings: [ignored, failed] } };
  const report = { projects: [project], overall_activity: { findings: [ignored, failed, unknown] } };
  assert.deepEqual(activityFindings(report, null).map(row => [row.finding.finding_id, row.project?.project_id ?? null]),
    [["failed", "first"], ["unknown", null]]);
  assert.deepEqual(activityFindings(report, "first").map(row => row.finding.finding_id), ["failed"]);
  assert.deepEqual(activityFindings(null, null), []);
});

test("evidence navigation finds a paired completion reference and never guesses an unrelated step", () => {
  const steps = [{ id: "start", start: { event_id: "start" }, completion: { event_id: "end" }, event: { event_id: "end" } },
    { id: "other", event: { event_id: "other" } }];
  assert.equal(evidenceStepId(steps, ["end"]), "start");
  assert.equal(evidenceStepId(steps, ["missing"]), null);
});
