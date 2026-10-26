# Dependency advisory checks

Run `npm run security:deps` after `npm ci`. CI checks production and development
dependencies through the official npm advisory endpoint. An unavailable or
malformed response fails the check.

## Patched development dependency

The ESLint React Hooks dependency chain previously resolved `zod` 4.4.3.
The lockfile now resolves 4.6.7, above the patched boundary 4.6.6 reported for
[GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5).
The update stays within the existing dependency range and adds no advisory
exception. Run the full check again after dependency resolution changes;
an earlier clean audit is not a permanent guarantee.

## Reviewed development-only advisory

[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)
affects deeply nested brace patterns. The advisory currently lists no patched
version. The installed chain is:

```text
eslint-config-next 16.4.1
  @next/eslint-plugin-next 16.4.1
    fast-glob 3.3.1
      micromatch 4.0.8
        braces 3.0.3
```

These packages are development-only. The Next lint plugin calls `fast-glob`
when `settings.next.rootDir` contains configured glob patterns. This repository
leaves that setting absent: the plugin returns ESLint's working directory
directly, without parsing it as a glob. HTTP data, Hook input and transcript
contents are not inputs to this configuration.

`scripts/lint-root-boundary.test.mjs` checks the configuration and exercises the
installed plugin with a deeply nested synthetic working-directory string.
`scripts/check_node_dependencies.mjs` accepts only this advisory, the listed
package versions and development-only lock entries. Any new advisory, changed
version, production exposure or failed boundary test fails the check and
requires review.

`npm audit` still reports the original findings. This review does not patch
`braces`, remove its advisory or establish safety for arbitrary use. Adding a
Next `rootDir` pattern requires replacing or updating this dependency chain
before enabling that configuration. Remove this scoped exception when a
patched upstream chain becomes available.
