# EvolveTrace for Codex

EvolveTrace captures supported Codex hook events, redacts sensitive values, and sends
the resulting audit event to the local FastAPI service at
http://127.0.0.1:8001/api/audit/events.

The hook process is best-effort: malformed input, a stopped backend, or a network
timeout always exits with code 0 so it never blocks the Codex task.

Start the backend from backend/, then install or link this plugin with the Codex
plugin manager. The local audit database is stored outside the repository by default.
