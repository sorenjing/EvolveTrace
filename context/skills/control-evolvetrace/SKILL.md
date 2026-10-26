---
name: control-evolvetrace
description: Use when the user wants to enable EvolveTrace, pause or resume execution collection, open its local workbench, or troubleshoot automatic service startup in Codex.
---

# Control EvolveTrace

Use the bundled stdlib Python controller at `../../../plugin/hooks/runtime_control.py`,
resolved relative to this Skill directory. Use its absolute path in commands and
quote paths with spaces. Do not assume the installed plugin lives in the current repo.

| Request | Controller arguments |
| --- | --- |
| First-time automatic startup | `enable --runtime "<EvolveTrace source directory>"` |
| Resume collection | `enable` |
| Pause collection | `pause` |
| Inspect collection and service | `status` |
| Open workbench in system browser | `open` |

Invoke as `python "<absolute-controller-path>" <arguments>`. Prefer Codex's browser
opening capability with the returned `base_url` when an in-app view is requested.

For first setup, use the user's supplied source directory or a verified current
EvolveTrace checkout. If neither is known, ask only for that directory; do not scan
the home directory. The runtime needs `backend/venv`, installed backend requirements
and `backend/static/index.html`. The plugin archive does not include these. Explain
missing prerequisites using the controller's result and the source checkout's RUN.md.
Do not install dependencies silently or claim installing the plugin installs a runtime.

`enable` persists opt-in and starts or reuses the local service. Subsequent trusted
SessionStart Hooks repeat the bounded health/start check. `pause` persists immediately
for future collection Hook invocations; it keeps existing evidence and the review
service running. In-flight events may finish. Context delivery and local PreToolUse
safety remain active. To disable the entire plugin, use Codex's plugin controls.

Check the command's exit code and JSON before reporting success. Collection preference,
service reachability and current event receipts are separate. `service=ready` does not
prove current Hook trust or full coverage. `configuration_error` pauses collection;
reconfigure explicitly to recover. Settings and service logs default to `~/.evolvetrace/`;
`EVOLVETRACE_CONTROL_DIR` selects an explicit alternate directory for both Hooks and CLI.

Never edit Codex trust hashes or enable Hooks on the user's behalf. After updating
the plugin, explain that modified Hook definitions require review through the host's
supported trust interface, then a new session. Do not call a natural-language command
a native settings toggle. No Agent messages, task execution, or source upload is part
of enabling collection.
