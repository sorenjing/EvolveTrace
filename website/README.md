# EvolveTrace public website

## Build and preview

From the repository root, install the separate website dependencies with `npm --prefix website ci`, then run `npm run site:build` and `npm run site:preview`. The preview listens only on `127.0.0.1:5181`; set `PORT` to use another port.

The static output is `website/dist/`. Upload the contents of that directory to any static host. No application backend, database, model API, or cloud-specific runtime is required.

## Source authority and downloads

The explicit documentation allowlist is in `project.mjs`. The build reads these documents and the source archive from `git HEAD`, so documents, downloads and source links describe one recorded commit. Commit reviewed project/document changes before rebuilding when you want them included. Untracked local runtime data is never added to the source ZIP.

The download page provides a versioned source ZIP, full commit SHA, size and SHA-256 checksum. It does not claim to provide an executable installer or a GitHub Release. The website's homepage and quick-start copy are authored in `project.mjs`.

## Hosting and migration

Set `WEBSITE_BASE=/repository-name/` when building for a subpath; default is `/`. Set `COMPANION_SITE_URL` to link to the other project's website; otherwise that link opens its GitHub repository. Run `npm --prefix website run check` to verify local links and download hashes.

Sites receives a separate generated-only checkout at the shared workspace's `.sites-hosting/evolvetrace-site/`. Its hosting identity stays there and is not needed by this portable source website. Publishing must use that same Site identity on subsequent updates.

These two project websites are public. Private interview and knowledge reading sites keep their existing audience.
