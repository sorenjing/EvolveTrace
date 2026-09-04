# EvolveTrace for Codex

EvolveTrace captures supported Codex hook events, redacts sensitive values, and sends the resulting audit event to the local FastAPI service at <http://127.0.0.1:8001/api/audit/events>.

Most hook collection is best-effort: malformed input, a stopped backend, or a network timeout exits with code 0 so it never blocks a normal Codex task. For PreToolUse Bash calls, Safety Sentinel first evaluates a small set of high-confidence destructive patterns. A blocked call emits Codex's documented denial JSON and is denied even when the local backend is unavailable; the sanitized denial record is still sent to the backend whenever it is reachable.

Start the dashboard with <code>./start.ps1</code>. In ChatGPT desktop Codex, use <code>./start.ps1 -NoBrowser</code> and ask <code>@Browser</code> to open <code>http://127.0.0.1:3000</code> for an in-app review workflow. The local audit database is stored outside the repository by default.
