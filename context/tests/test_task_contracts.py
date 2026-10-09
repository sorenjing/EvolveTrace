from datetime import datetime, timezone

import pytest

from ai_context_kit.task_contracts import (
    AcceptanceCriterion,
    ContextReceipt,
    TaskEnvelope,
    TaskEnvelopeV2,
    canonical_digest,
    task_envelope_from_dict,
)


def test_task_envelope_serializes_without_provider_prompt_fields() -> None:
    envelope = TaskEnvelope.create(
        task_id="task-123",
        target_project="content-workbench",
        intent="Refresh the current interview project view",
        requested_by="human",
        platform="codex",
        created_at=datetime(2026, 9, 16, tzinfo=timezone.utc),
    )

    assert envelope.to_dict() == {
        "schema": "task-envelope/v1",
        "task_id": "task-123",
        "target_project": "content-workbench",
        "intent": "Refresh the current interview project view",
        "requested_by": "human",
        "platform": "codex",
        "created_at": "2026-09-16T00:00:00+00:00",
    }


def test_task_envelope_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone"):
        TaskEnvelope.create(
            task_id="task-123",
            target_project="content-workbench",
            intent="Refresh project view",
            requested_by="human",
            platform="codex",
            created_at=datetime(2026, 9, 16),
        )


def test_receipt_rejects_initial_claim_jump() -> None:
    with pytest.raises(ValueError, match="initial status"):
        ContextReceipt.create(
            receipt_id="receipt-123",
            task_id="task-123",
            attempt_id="attempt-1",
            bundle_id="bundle-123",
            platform="codex",
            adapter="codex-hooks",
            status="effective",
            delivered_source_ids=("source-1",),
            loaded_skill_ids=(),
        )


def test_delivered_receipt_requires_a_source_identifier() -> None:
    with pytest.raises(ValueError, match="source"):
        ContextReceipt.create(
            receipt_id="receipt-123",
            task_id="task-123",
            attempt_id="attempt-1",
            bundle_id="bundle-123",
            platform="codex",
            adapter="codex-hooks",
            status="delivered",
            delivered_source_ids=(),
            loaded_skill_ids=(),
            execution_profile_id=None,
        )


def test_receipt_advances_one_observable_claim_at_a_time() -> None:
    receipt = ContextReceipt.create(
        receipt_id="receipt-123",
        task_id="task-123",
        attempt_id="attempt-1",
        bundle_id="bundle-123",
        platform="codex",
        adapter="codex-hooks",
        status="delivered",
        delivered_source_ids=("source-1",),
        loaded_skill_ids=("skill-1",),
        execution_profile_id="codex-local",
    )

    acknowledged = receipt.advance("acknowledged")
    assert acknowledged.status == "acknowledged"
    assert acknowledged.delivered_source_ids == ("source-1",)
    assert acknowledged.execution_profile_id == "codex-local"
    with pytest.raises(ValueError, match="one level"):
        acknowledged.advance("effective")


def test_canonical_digest_is_key_order_independent() -> None:
    assert canonical_digest({"b": 2, "a": 1}) == canonical_digest({"a": 1, "b": 2})


def test_v2_envelope_serializes_structured_acceptance_contract() -> None:
    criterion = AcceptanceCriterion.from_dict({"criterion_id":"tests","type":"command_exit_zero","required":True,"description":"Tests pass","config":{"command":"python -m pytest -q"}})
    envelope = TaskEnvelopeV2.create(task_id="task-2", target_project="demo", target_repositories=("projects/demo",), intent="Verify change", requested_by="human", platform="codex", constraints=("Keep compatibility",), acceptance_criteria=(criterion,), created_at=datetime(2026, 9, 17, tzinfo=timezone.utc))
    payload = envelope.to_dict()
    assert payload["schema"] == "task-envelope/v2"
    assert payload["acceptance_criteria"][0]["criterion_id"] == "tests"
    assert task_envelope_from_dict(payload) == envelope


@pytest.mark.parametrize("payload", [
    {"criterion_id":"x","type":"unknown","required":True,"description":"x","config":{}},
    {"criterion_id":"x","type":"file_exists","required":True,"description":"x","config":{"path":"../secret"}},
    {"criterion_id":"x","type":"path_scope","required":True,"description":"x","config":{"allowed_prefixes":[r"C:\\private"]}},
])
def test_criterion_rejects_invalid_values(payload) -> None:
    with pytest.raises(ValueError):
        AcceptanceCriterion.from_dict(payload)
