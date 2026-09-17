import pytest

from harness.models import ContextReceipt, TaskContract
from harness.repository import HarnessRepository


def _configured(tmp_path):
    repository = HarnessRepository(tmp_path / "harness.db")
    snapshot = repository.import_context_snapshot(
        {
            "schema_version": "context-bundle/v1",
            "project": "sample-app",
            "generated_at": "2026-09-16T00:00:00+00:00",
            "freshness": "current",
            "observed_scope": ["sample-app"],
            "repositories": [{"name": "sample-app", "relative_path": "sample-app"}],
            "context": {"automatic": "facts", "manual": "notes"},
            "bundle_id": "ctx_1",
        }
    )
    task = repository.create_task(
        TaskContract.create(
            task_id="task-1",
            title="Bind context",
            goal="Observe delivery",
            target_repositories=("sample-app",),
            constraints=(),
            acceptance_criteria=(),
            open_questions=(),
            risk_level="normal",
            status="ready",
            context_snapshot_id=snapshot.snapshot_id,
        )
    )
    return repository, snapshot, task


def _payload(snapshot_id: str, *, status: str = "delivered"):
    return {
        "schema": "context-receipt/v1",
        "receipt_id": "receipt-1",
        "task_id": "task-1",
        "context_snapshot_id": snapshot_id,
        "attempt_id": "unassigned",
        "bundle_id": "ctx_1",
        "platform": "codex",
        "adapter": "evolvetrace-http",
        "status": status,
        "delivered_source_ids": ["context:sample-app:rendered"],
        "loaded_skill_ids": ["running-context-aware-tasks"],
    }


def test_receipt_ingestion_is_idempotent(tmp_path) -> None:
    repository, snapshot, _ = _configured(tmp_path)
    receipt = ContextReceipt.from_payload(_payload(snapshot.snapshot_id))

    first = repository.upsert_context_receipt(receipt)
    second = repository.upsert_context_receipt(receipt)

    assert first == second
    assert repository.list_context_receipts("task-1") == [first]


def test_receipt_cannot_regress_or_skip_delivery_levels(tmp_path) -> None:
    repository, snapshot, _ = _configured(tmp_path)
    delivered = repository.upsert_context_receipt(
        ContextReceipt.from_payload(_payload(snapshot.snapshot_id))
    )
    acknowledged = delivered.advance("acknowledged", attempt_id="run-1")
    repository.upsert_context_receipt(acknowledged)

    with pytest.raises(ValueError, match="regress"):
        repository.upsert_context_receipt(delivered)
    with pytest.raises(ValueError, match="one level"):
        repository.upsert_context_receipt(acknowledged.advance("evidenced").advance("effective"))


@pytest.mark.parametrize("forbidden", ["prompt", "checkpoint_data", "review_comment"])
def test_receipt_rejects_unbounded_or_private_fields(tmp_path, forbidden) -> None:
    _, snapshot, _ = _configured(tmp_path)
    payload = _payload(snapshot.snapshot_id)
    payload[forbidden] = "private content"

    with pytest.raises(ValueError, match="unknown fields"):
        ContextReceipt.from_payload(payload)


def test_receipt_rejects_secret_like_values(tmp_path) -> None:
    _, snapshot, _ = _configured(tmp_path)
    payload = _payload(snapshot.snapshot_id)
    payload["delivered_source_ids"] = ["token=private-secret-value"]

    with pytest.raises(ValueError, match="sensitive"):
        ContextReceipt.from_payload(payload)


def test_receipt_bundle_id_must_match_bound_snapshot(tmp_path) -> None:
    repository, snapshot, _ = _configured(tmp_path)
    payload = _payload(snapshot.snapshot_id)
    payload["bundle_id"] = "ctx_other"

    with pytest.raises(ValueError, match="bundle_id"):
        repository.upsert_context_receipt(ContextReceipt.from_payload(payload))
