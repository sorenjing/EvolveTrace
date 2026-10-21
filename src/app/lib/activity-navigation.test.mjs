import assert from "node:assert/strict";
import test from "node:test";
import { projectForSession } from "./activity-navigation.ts";

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
