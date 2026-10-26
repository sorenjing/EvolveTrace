# EvolveTrace Hook collector

This directory contains the collector and deterministic safety policy used by the repository-root unified plugin. Install the archive described in [the consolidation guide](../docs/consolidation.md); its configuration is [`hooks/hooks.json`](../hooks/hooks.json).

The standalone audit-only plugin packaging has been retired. Existing users should enable the unified plugin and disable the old installation to avoid duplicate capture. This source change does not update an already installed plugin.

EvolveTrace captures supported Codex hook events, redacts sensitive values, and sends the resulting audit event to the local FastAPI service at <http://127.0.0.1:8001/api/audit/events>.

Most hook collection is best-effort: malformed input, a stopped backend, or a network timeout exits with code 0 so it never blocks a normal Codex task. For PreToolUse Bash calls, Safety Sentinel first evaluates a small set of high-confidence destructive patterns. A blocked call emits Codex's documented denial JSON and is denied even when the local backend is unavailable; the sanitized denial record is still sent to the backend whenever it is reachable.

Start the dashboard with <code>./start.ps1</code>. In ChatGPT desktop Codex, use <code>./start.ps1 -NoBrowser</code> and ask <code>@Browser</code> to open <code>http://127.0.0.1:8001</code> for an in-app review workflow. Port 3000 is only for Next.js hot-reload development. The local audit database is stored outside the repository by default.

After runtime dependencies and the static UI are prepared, opt into automatic startup
with `python plugin/hooks/runtime_control.py enable --runtime .` from the source root.
The packaged `control-evolvetrace` Skill provides enable, pause, status and open commands.
Trusted SessionStart Hooks reuse or start the local service. Pause keeps Context,
Safety Sentinel, historical evidence and the running workbench. No runtime dependencies
are shipped in the plugin archive; see [RUN.md](../RUN.md) for setup and recovery.

See the [usage guide](../docs/usage.md) and [observability guide](../docs/observability.md) for setup, evidence checks, and troubleshooting.
The [Hook event contract](../docs/hook-event-contract.md) lists the packaged
event names, stored fields, and evidence limits. The [evidence validation
procedure](../docs/hook-evidence-contract.md) covers synthetic tests and live
checks for a particular installed version.
