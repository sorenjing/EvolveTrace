import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness.models import ContextSnapshot, TaskContract
from harness.repository import HarnessRepository


def make_bundle():
    return {
        "schema_version": "context-bundle/v1",
        "project": "sample-app",
        "generated_at": "2026-09-09T00:00:00+00:00",
        "freshness": "current",
        "observed_scope": ["sample-app"],
        "repositories": [{"name": "sample-app", "relative_path": "sample-app"}],
        "context": {"automatic": "facts", "manual": "notes", "global": "rules"},
    }


def make_task(**overrides):
    values = {
        "title": "Add verified export",
        "goal": "Export a stable artifact",
        "target_repositories": ["sample-app"],
        "constraints": [],
        "acceptance_criteria": ["Tests pass"],
        "open_questions": [],
        "risk_level": "normal",
        "status": "ready",
    }
    values.update(overrides)
    return TaskContract.create(**values)


def test_task_cannot_be_ready_with_open_questions():
    with pytest.raises(ValueError, match="open questions"):
        make_task(open_questions=["Which format?"])


def test_snapshot_digest_is_stable():
    first = ContextSnapshot.from_bundle({"b": 2, "a": 1}, source="file-import")
    second = ContextSnapshot.from_bundle({"a": 1, "b": 2}, source="file-import")
    assert first.content_digest == second.content_digest


def test_run_binds_task_snapshot_and_session(tmp_path):
    repository = HarnessRepository(tmp_path / "harness.db")
    snapshot = repository.import_context_snapshot(make_bundle())
    task = repository.create_task(make_task(context_snapshot_id=snapshot.snapshot_id))
    run = repository.create_run(task.task_id, snapshot.snapshot_id)
    bound = repository.bind_session(run.run_id, "session-1", "sample-app")
    assert bound.task_id == task.task_id
    assert bound.context_snapshot_id == snapshot.snapshot_id
    assert bound.session_id == "session-1"
