# Public Project Website Implementation Plan

> For agentic workers: execute inline in this session with the executing-plans workflow.

**Goal:** Provide a public, portable project website with working versioned source downloads.

**Architecture:** Keep all website authoring in website/. Read only an explicit list of existing public Markdown files. Export a static dist and a Git source archive from the recorded commit; publish a generated-only checkout to Sites.

**Tech stack:** Node.js, markdown-it, markdown-it-anchor, native HTML/CSS/JavaScript.

**Spec:** ../specs/2026-10-08-project-website.md

## Global constraints

- Preserve local CLI/backend behavior and existing docs as the authority.
- Use source-download labels and real Git revisions; do not fabricate releases.
- Publish only explicit website output and publicly committed source archives.
- No private snapshots, runtime databases, credentials, or telemetry.

## Tasks

- [x] Create site build, distinct project theme, homepage, quick start, download and document pages.
- [x] Verify source archives, source provenance, all local links and assets.
- [x] Add repository entry points and portable build instructions.
- [x] Publish the requested public project site and confirm successful deployment.

## Execution decisions

- Work in the existing clean checkouts; website/ is independent of the runtime source.
- Use build checks and browser smoke verification for the static changes, not unrelated runtime test suites.
- Keep source-repository changes reviewable in the working tree; publishing pushes only generated static checkouts.

## Verification results

- Static build: 12 pages per site; local links, fragment targets and ZIP hashes verified.
- Browser smoke: both source downloads completed; mobile menu and document navigation work. AI Context Kit download layout was corrected and verified at a 390px viewport without horizontal page overflow.
- EvolveTrace root ESLint: passes. Markdown build dependencies installed from the official registry with zero reported audit findings.
- Archives include LICENSE and exclude private context, virtual environments, node_modules and local databases.
- Native Sites deployment succeeded with public audience: https://sorenjing-evolvetrace.uas857030604.chatgpt.site
