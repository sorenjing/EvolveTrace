"""Hint that a shared context workspace is available, without reading memory."""

from __future__ import annotations

import json
from pathlib import Path
import sys


def main() -> None:
    try:
        event = json.load(sys.stdin)
        cwd = event.get("cwd")
        if not isinstance(cwd, str):
            return
        current = Path(cwd).resolve()
        if not current.is_dir():
            return
        if not any((candidate / ".aictx.toml").is_file() for candidate in (current, *current.parents)):
            return
    except (OSError, ValueError, TypeError):
        return
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": (
                "AI Context Kit: a shared workspace is configured in the current directory "
                "or a nearest ancestor. Before broad repository analysis, use the "
                "manage-ai-context skill to locate that workspace and read its global, "
                "workspace, and selected project memory. Check freshness first. "
                "This hook has not read or included memory content."
            ),
        }
    }))


if __name__ == "__main__":
    main()
