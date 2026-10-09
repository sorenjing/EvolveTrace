"""Delegate context loading to the CLI, including separately installed runtimes."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys


def main() -> None:
    try:
        from ai_context_kit.context_delivery import session_start
    except ImportError:
        command = shutil.which("aictx")
        if command:
            try:
                result = subprocess.run([command, "session-start"], input=sys.stdin.read(65537),
                                        text=True, capture_output=True, check=False, timeout=15)
                if result.returncode == 0:
                    if result.stdout:
                        payload = json.loads(result.stdout)
                        if not isinstance(payload, dict):
                            raise ValueError("invalid hook output")
                        print(json.dumps(payload, ensure_ascii=True), flush=True)
                    return
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
            print(json.dumps({"systemMessage": "AI Context Kit: CLI failed or is outdated. Upgrade the CLI; no context was confirmed returned."}))
        else:
            print(json.dumps({"systemMessage": "AI Context Kit: CLI unavailable. Install aictx and ensure it is on PATH; no context was loaded."}))
        return
    session_start()


if __name__ == "__main__":
    main()
