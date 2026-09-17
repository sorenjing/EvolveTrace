import pytest

from harness.models import AcceptanceCriterion, EvaluationResult, ReviewDecision, TaskContract


def test_structured_criterion_round_trips_through_task_contract() -> None:
    criterion = AcceptanceCriterion.from_payload({
        "criterion_id": "backend-tests",
        "type": "command_exit_zero",
        "required": True,
        "description": "Backend tests pass",
        "config": {"command": "python -m pytest -q"},
    })
    task = TaskContract.create(
        task_id="task-1", title="Evaluate", goal="Collect evidence",
        target_repositories=["projects/demo"], constraints=[],
        acceptance_criteria=[criterion.to_dict()], open_questions=[],
        risk_level="normal", status="ready",
    )
    assert task.to_dict()["acceptance_criteria"] == [criterion.to_dict()]


@pytest.mark.parametrize("payload", [
    {"criterion_id": "x", "type": "unknown", "required": True, "description": "x", "config": {}},
    {"criterion_id": "x", "type": "file_exists", "required": True, "description": "x", "config": {"path": "../secret"}},
    {"criterion_id": "x", "type": "path_scope", "required": True, "description": "x", "config": {"allowed_prefixes": ["C:\\temp"]}},
])
def test_structured_criterion_rejects_invalid_payload(payload) -> None:
    with pytest.raises(ValueError):
        AcceptanceCriterion.from_payload(payload)


def test_task_rejects_duplicate_criterion_ids() -> None:
    item = {"criterion_id": "same", "type": "manual", "required": True, "description": "Review", "config": {}}
    with pytest.raises(ValueError, match="duplicate"):
        TaskContract.create(title="x", goal="x", target_repositories=["demo"], constraints=[], acceptance_criteria=[item, item], open_questions=[], risk_level="normal")


def test_evaluation_and_review_models_are_explicit() -> None:
    result = EvaluationResult.create(
        task_id="task-1", run_id="run-1", criterion_id="backend-tests",
        evaluator_id="verification", evaluator_version="1", status="passed",
        severity="blocking", summary="Verification passed", evidence_refs=["event-1"],
        expected="exit 0", actual="exit 0", evaluation_id="eval-1",
    )
    decision = ReviewDecision.create(
        task_id="task-1", run_id="run-1", outcome="accepted", note="Reviewed",
        evaluation_ids=[result.evaluation_id], actor="human", decision_id="decision-1",
    )
    assert result.to_dict()["evidence_refs"] == ["event-1"]
    assert decision.to_dict()["outcome"] == "accepted"
