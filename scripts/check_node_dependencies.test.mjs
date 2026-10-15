import assert from "node:assert/strict";
import test from "node:test";
import { assessAudit } from "./check_node_dependencies.mjs";

const advisory = "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm";
const lock = { packages: { "node_modules/braces": { version: "3.0.3", dev: true } } };
const report = () => ({ metadata: { vulnerabilities: { total: 1 } }, vulnerabilities: {
  braces: { nodes: ["node_modules/braces"], via: [{ url: advisory }] },
} });

test("recognizes only the reviewed development dependency and fixed version", () => {
  assert.equal(assessAudit(report(), lock).length, 1);
  assert.deepEqual(assessAudit({ metadata: { vulnerabilities: { total: 0 } }, vulnerabilities: {} }, lock), []);
});

test("fails on another advisory, production exposure, or changed dependency version", () => {
  const other = report();
  other.vulnerabilities.braces.via.push({ url: "https://example.invalid/unreviewed" });
  assert.throws(() => assessAudit(other, lock));
  assert.throws(() => assessAudit(report(), { packages: { "node_modules/braces": { version: "3.0.3" } } }));
  assert.throws(() => assessAudit(report(), { packages: { "node_modules/braces": { version: "3.0.4", dev: true } } }));
});

test("a malformed advisory response never counts as clean", () => {
  assert.throws(() => assessAudit({ error: { code: "E404" } }, lock));
  assert.throws(() => assessAudit({ metadata: { vulnerabilities: { total: 1 } }, vulnerabilities: {} }, lock));
});

test("truncated and circular advisory chains cannot use the reviewed exception", () => {
  const truncated = report();
  truncated.vulnerabilities.braces.via = ["fast-glob"];
  assert.throws(() => assessAudit(truncated, lock));
  const circular = report();
  circular.vulnerabilities.braces.via = ["braces"];
  assert.throws(() => assessAudit(circular, lock));
});
