import pytest

from harness.models import ExecutionProfile
from harness.repository import HarnessRepository


def payload():
    return {
        "schema": "execution-profile/v1",
        "profile_id": "codex-local",
        "platform": "codex",
        "harness": "codex-work",
        "adapter": "openai-plugin",
        "adapter_version": "1.0.0",
        "provider": "openai",
        "model": "gpt-test",
        "capabilities": ["skills", "mcp", "skills"],
        "policy_profile": "local-reviewed",
    }


def test_execution_profile_is_strict_normalized_and_idempotent(tmp_path) -> None:
    repository = HarnessRepository(tmp_path / "harness.db")
    profile = ExecutionProfile.from_payload(payload())
    assert profile.capabilities == ("mcp", "skills")
    assert repository.upsert_execution_profile(profile) == profile
    assert repository.upsert_execution_profile(profile) == profile
    assert repository.get_execution_profile("codex-local") == profile


def test_execution_profile_rejects_private_or_conflicting_content(tmp_path) -> None:
    private = payload()
    private["prompt"] = "private"
    with pytest.raises(ValueError, match="unknown"):
        ExecutionProfile.from_payload(private)

    repository = HarnessRepository(tmp_path / "harness.db")
    repository.upsert_execution_profile(ExecutionProfile.from_payload(payload()))
    changed = payload()
    changed["model"] = "another-model"
    with pytest.raises(ValueError, match="immutable"):
        repository.upsert_execution_profile(ExecutionProfile.from_payload(changed))

