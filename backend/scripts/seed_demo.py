"""Insert a deterministic local session for the EvolveTrace demo."""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.audit_service import AuditService


def main() -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    service = AuditService()
    session_id = "demo-evolvetrace-session"
    events = [
        {
            "event_id": "demo-001",
            "session_id": session_id,
            "turn_id": "turn-demo",
            "sequence": 1,
            "hook_event_name": "UserPromptSubmit",
            "timestamp": timestamp,
            "cwd": "D:/demo/sample-project",
            "prompt": "Review the auth change and run the relevant tests.",
        },
        {
            "event_id": "demo-002",
            "session_id": session_id,
            "turn_id": "turn-demo",
            "sequence": 2,
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "timestamp": timestamp,
            "cwd": "D:/demo/sample-project",
            "tool_input": {"command": "git status && git diff -- backend/auth.py"},
        },
        {
            "event_id": "demo-003",
            "session_id": session_id,
            "turn_id": "turn-demo",
            "sequence": 3,
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "timestamp": timestamp,
            "cwd": "D:/demo/sample-project",
            "tool_input": {"command": "git reset --hard HEAD"},
            "tool_response": {"exit_code": 0, "stdout": "working tree reset"},
        },
        {
            "event_id": "demo-004",
            "session_id": session_id,
            "turn_id": "turn-demo",
            "sequence": 4,
            "hook_event_name": "PostToolUse",
            "tool_name": "Bash",
            "timestamp": timestamp,
            "cwd": "D:/demo/sample-project",
            "tool_response": {"exit_code": 1, "stderr": "pytest failed"},
            "status": "failed",
        },
    ]
    for event in events:
        service.ingest(event)
    print(f"Seeded EvolveTrace session: {session_id}")


if __name__ == "__main__":
    main()
