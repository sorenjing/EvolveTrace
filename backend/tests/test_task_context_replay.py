import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from audit.repository import AuditRepository
from scripts.seed_demo import replay_fixture
from harness.repository import HarnessRepository


def test_task_context_run_fixture_replays(tmp_path):
    result = replay_fixture(HarnessRepository(tmp_path / "harness.db"), AuditRepository(tmp_path / "audit.db"))
    assert result["task"]["status"] == "active"
    assert result["context_snapshot"]["freshness"] == "current"
    assert result["run"]["session_id"] == "demo-session"
    assert len(result["audit_session"]["events"]) >= 2
