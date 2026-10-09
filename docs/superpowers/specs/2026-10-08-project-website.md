# Public project website

Approved scope: a separate public static project homepage, quick start, selected existing documentation, download page, and changelog. Keep the application runtime local and unchanged.

Use a small Node.js Markdown build in website/. Generate HTML/CSS/JavaScript and a source ZIP from a specific Git commit. No backend, account integration, private workspace data, or live agent events are included. GitHub is the source authority; preserve existing Markdown documents.

Downloads must identify source archives and required dependencies. No executable installer or published release may be implied when unavailable. Show full commit, SHA-256, source version and license. All download bytes are hosted with the static site.

Document links must resolve to generated pages or the original GitHub source. Pages must remain readable on mobile and accessible by keyboard. Build output can move to another static host with an explicit base path.

Verification: build both websites, check all local links and assets, inspect ZIP entries and hashes, exercise navigation and download in a browser, verify native hosting success and public access.
