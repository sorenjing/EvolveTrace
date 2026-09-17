import json
from pathlib import Path

from harness.models import ContextReceipt, TaskContract
from harness.repository import HarnessRepository
from services.harness_service import HarnessService


def test_failed_then_corrected_run_advances_receipt_to_effective(tmp_path):
    fixture = json.loads((Path(__file__).parent / "fixtures" / "evidence-eval-regression.json").read_text(encoding="utf-8"))
    repository = HarnessRepository(tmp_path / "harness.db")
    service = HarnessService(repository)
    snapshot = repository.import_context_snapshot(fixture["context_bundle"])
    task = repository.create_task(TaskContract.create(context_snapshot_id=snapshot.snapshot_id, **fixture["task"]))
    repository.upsert_context_receipt(ContextReceipt.from_payload({"schema":"context-receipt/v1","receipt_id":"receipt-example","task_id":task.task_id,"context_snapshot_id":snapshot.snapshot_id,"attempt_id":"unassigned","bundle_id":"ctx-example","platform":"codex","adapter":"test","status":"delivered","delivered_source_ids":["context:example"]}))
    first = repository.create_run(task.task_id, snapshot.snapshot_id); repository.set_run_status(first.run_id, "completed")
    repository.upsert_context_receipt(repository.list_context_receipts(task.task_id)[0].advance("acknowledged", attempt_id=first.run_id))
    first_eval = service.evaluate_run(task.task_id, first.run_id, {"events": fixture["first_events"]})
    service.record_review(task.task_id, first.run_id, {"outcome":"needs_fix","note":"tests missing","evaluation_ids":[x["evaluation_id"] for x in first_eval["evaluations"]],"actor":"human"})
    repository.set_task_status(task.task_id, "active")
    second = repository.create_run(task.task_id, snapshot.snapshot_id); repository.set_run_status(second.run_id, "completed")
    second_eval = service.evaluate_run(task.task_id, second.run_id, {"events": fixture["corrected_events"]})
    service.record_review(task.task_id, second.run_id, {"outcome":"accepted","note":"verified","evaluation_ids":[x["evaluation_id"] for x in second_eval["evaluations"]],"actor":"human"})
    result = service.compare_runs(task.task_id, first.run_id, second.run_id)
    assert result["status"] == "effective"
    assert repository.list_context_receipts(task.task_id)[0].status == "effective"
