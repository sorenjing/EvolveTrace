"""Replay the sanitized Hook fixture into the local audit database."""

import json
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.audit_service import AuditService
from services.harness_service import HarnessService
from harness.repository import HarnessRepository
from audit.repository import AuditRepository


FIXTURE = BACKEND / "tests" / "fixtures" / "codex_hook_session.json"
TASK_FIXTURE = BACKEND / "tests" / "fixtures" / "task_context_run.json"
BUNDLE_FIXTURE = BACKEND / "tests" / "fixtures" / "context_bundle_v1.json"


def replay_fixture(harness_repository: HarnessRepository, audit_repository: AuditRepository) -> dict:
    """Replay only the public synthetic Task → Context → Run fixture."""
    harness = HarnessService(harness_repository)
    fixture = json.loads(TASK_FIXTURE.read_text(encoding="utf-8"))
    bundle = json.loads(BUNDLE_FIXTURE.read_text(encoding="utf-8"))
    snapshot = harness.import_context_snapshot(bundle)
    task = harness.create_task({**fixture["task"], "context_snapshot_id": snapshot["snapshot_id"]})
    harness.activate_task(task["task_id"], "sample-app")
    audit = AuditService(audit_repository, run_resolver=harness.resolve_or_create_run)
    run = None
    for event in fixture["audit_events"]:
        run = audit.ingest(event)["run"] or run
    return {"task": harness.get_task(task["task_id"]), "context_snapshot": snapshot, "run": run, "audit_session": audit.get_session("demo-session")}


def main() -> None:
    result = replay_fixture(HarnessRepository(BACKEND / ".demo-harness.db"), AuditRepository(BACKEND / ".demo-audit.db"))
    print(f"Replayed {len(result['audit_session']['events'])} synthetic events for demo-session")


if __name__ == "__main__":
    main()
