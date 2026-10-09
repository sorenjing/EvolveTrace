# Security policy

Do not open a public issue for a vulnerability that could expose local files, secrets, or paths outside the configured workspace. Report it privately through GitHub's security advisory feature for this repository.

AI Context Kit's local collection, update, export, and publication-preparation commands are designed to operate offline. Unexpected network activity from those commands, traversal outside the resolved workspace, symlink traversal, or reading common secret files should be treated as security bugs.

The optional MCP server performs read-only requests to `api.github.com` for one explicitly configured repository. It must not accept arbitrary repository names or paths from tool callers, expose `GITHUB_TOKEN`, or return files outside the published index. Report violations privately.

Response-size, request-timeout, and per-worker in-flight limits are security boundaries. Deployments must size worker count and `AICTX_MAX_IN_FLIGHT` together instead of treating the per-process semaphore as a global limit.
