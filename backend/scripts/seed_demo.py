"""Replay the sanitized Hook fixture into the local audit database."""

import json
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.audit_service import AuditService


FIXTURE = BACKEND / "tests" / "fixtures" / "codex_hook_session.json"


def main() -> None:
    service = AuditService()
    events = json.loads(FIXTURE.read_text(encoding="utf-8"))
    persisted = sum(bool(service.ingest(event)["persisted"]) for event in events)
    print(f"Replayed {persisted} EvolveTrace events for fixture-session")


if __name__ == "__main__":
    main()
