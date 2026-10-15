import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const versions = {
  "eslint-config-next": "16.4.1", "@next/eslint-plugin-next": "16.4.1",
  "fast-glob": "3.3.1", micromatch: "4.0.8", braces: "3.0.3",
};
const advisory = "https://github.com/advisories/GHSA-vfj7-8cjw-p6xm";

export function assessAudit(report, lock) {
  if (report.error || !report.metadata?.vulnerabilities || !report.vulnerabilities
      || typeof report.vulnerabilities !== "object" || Array.isArray(report.vulnerabilities)) {
    throw new Error("Dependency audit did not return a complete advisory report.");
  }
  if (!Number.isInteger(report.metadata.vulnerabilities.total)
      || report.metadata.vulnerabilities.total !== Object.keys(report.vulnerabilities).length) {
    throw new Error("Dependency audit totals do not match its findings.");
  }
  const reviewed = [];
  for (const [name, finding] of Object.entries(report.vulnerabilities)) {
    if (!Object.hasOwn(versions, name) || !Array.isArray(finding?.nodes) || !finding.nodes.length
        || !Array.isArray(finding.via) || !finding.via.length) {
      throw new Error(`Unreviewed dependency finding: ${name}`);
    }
    for (const node of finding.nodes) {
      const entry = lock.packages?.[node];
      if (node !== `node_modules/${name}` || !entry?.dev || entry.version !== versions[name]) {
        throw new Error(`Reviewed dependency scope or version changed: ${name}`);
      }
    }
    for (const cause of finding.via) {
      if (typeof cause === "string" ? !Object.hasOwn(versions, cause) : cause?.url !== advisory) {
        throw new Error(`Unreviewed advisory: ${name}`);
      }
    }
    reviewed.push(name);
  }
  const visiting = new Set();
  const proven = new Set();
  function trace(name) {
    if (proven.has(name)) return;
    if (visiting.has(name) || !Object.hasOwn(report.vulnerabilities, name)) {
      throw new Error("Dependency advisory chain is circular or incomplete.");
    }
    visiting.add(name);
    for (const cause of report.vulnerabilities[name].via) {
      if (typeof cause === "string") trace(cause);
    }
    visiting.delete(name);
    proven.add(name);
  }
  reviewed.forEach(trace);
  return reviewed;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const root = fileURLToPath(new URL("../", import.meta.url));
  const boundary = spawnSync(process.execPath, ["--test", "scripts/lint-root-boundary.test.mjs"], { cwd: root, encoding: "utf8" });
  if (boundary.status !== 0) throw new Error("The reviewed lint input boundary no longer holds.");
  if (!process.env.npm_execpath) throw new Error("Run through npm run security:deps.");
  const audit = spawnSync(process.execPath, [process.env.npm_execpath, "audit", "--registry=https://registry.npmjs.org", "--json"], {
    cwd: root, encoding: "utf8", timeout: 60000, maxBuffer: 10 * 1024 * 1024,
  });
  if (![0, 1].includes(audit.status)) throw new Error("Dependency advisory service is unavailable.");
  const reviewed = assessAudit(JSON.parse(audit.stdout), JSON.parse(readFileSync(new URL("../package-lock.json", import.meta.url))));
  console.log(reviewed.length
    ? `No unreviewed advisories. ${reviewed.length} development-chain findings remain for GHSA-vfj7-8cjw-p6xm; see docs/dependency-security.md.`
    : "No dependency advisories reported.");
}
