import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import test from "node:test";
import config from "../eslint.config.mjs";

test("Next lint root discovery never parses working directory as a glob", () => {
  for (const entry of config) assert.equal(entry.settings?.next?.rootDir, undefined);
  const require = createRequire(import.meta.url);
  const { getRootDirs } = require(join(dirname(require.resolve("@next/eslint-plugin-next")), "utils/get-root-dirs.js"));
  const cwd = "/synthetic/" + "{".repeat(10000);
  assert.deepEqual(getRootDirs({ cwd, settings: {} }), [cwd]);
});
