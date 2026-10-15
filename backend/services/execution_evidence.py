"""Shared, cached interpretation for activity statistics and task evaluation."""

from pathlib import Path

from audit.execution_context import resolve_directories
from audit.workspace import WorkspaceRepository


def resolve_execution_evidence(events: list[dict], repository: WorkspaceRepository | None = None) -> tuple[list[dict], dict]:
    refs = [event["event_id"] for event in events]
    directories = repository.execution_directories(refs) if repository else {}
    results = repository.execution_results(refs) if repository else {}
    pending, scan = resolve_directories([event for event in events if event["event_id"] not in results])
    for event in pending:
        previous = directories.get(event["event_id"])
        if previous and event["_directory_source"] == "execution_record" and Path(previous) != Path(event["cwd"]):
            event["_execution_result"] = {"outcome": "unknown", "exit_code": None, "duration_ms": None,
                                           "started_at": None, "completed_at": None, "conflict": True}
            event["cwd"] = previous
    if repository:
        repository.cache_execution_directories(pending)
        repository.cache_execution_results(pending)
    resolved = {event["event_id"]: event for event in pending}
    output = []
    for event in events:
        identity = event["event_id"]
        value = resolved.get(identity, {**event, "_directory_source": "hook_cwd"})
        if identity in directories:
            value.update(cwd=directories[identity], _directory_source="execution_record")
        if identity in results:
            value["_execution_result"] = results[identity]
        output.append(value)
    return output, scan
