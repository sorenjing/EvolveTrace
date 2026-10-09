from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from threading import Thread

from ai_context_kit.evolvetrace_client import build_task_payload, submit_task
from ai_context_kit.task_contracts import AcceptanceCriterion, ContextReceipt, TaskEnvelope, TaskEnvelopeV2


def test_v2_payload_preserves_structured_contract() -> None:
    criterion = AcceptanceCriterion.from_dict({"criterion_id":"tests","type":"command_exit_zero","required":True,"description":"Tests pass","config":{"command":"python -m pytest -q"}})
    envelope = TaskEnvelopeV2.create(task_id="task-2", target_project="demo", target_repositories=("projects/demo",), intent="Verify", requested_by="human", platform="codex", constraints=("Keep compatibility",), acceptance_criteria=(criterion,))
    payload = build_task_payload(envelope, "snapshot-1", ["projects/demo"])
    assert payload["acceptance_criteria"] == [criterion.to_dict()]
    assert payload["target_repositories"] == ["projects/demo"]


def test_submit_task_uses_existing_harness_contracts_in_order() -> None:
    requests: list[tuple[str, dict[str, object]]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers["Content-Length"])
            payload = json.loads(self.rfile.read(length))
            requests.append((self.path, payload))
            responses = {
                "/api/harness/context-snapshots": {"snapshot_id": "snapshot-1"},
                "/api/harness/tasks": {"task_id": "task-1"},
                "/api/harness/context-receipts": {"receipt_id": "receipt-1"},
                "/api/harness/tasks/task-1/activate": {"task_id": "task-1"},
            }
            body = json.dumps(responses[self.path]).encode()
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever)
    thread.start()
    try:
        envelope = TaskEnvelope.create(
            task_id="task-1",
            target_project="demo",
            intent="Refresh project view",
            requested_by="human",
            platform="codex",
        )
        receipt = ContextReceipt.create(
            receipt_id="receipt-1",
            task_id="task-1",
            attempt_id="unassigned",
            bundle_id="ctx_1",
            platform="codex",
            adapter="unassigned",
            status="generated",
            delivered_source_ids=("context:demo:rendered",),
            loaded_skill_ids=(),
        )
        bundle = {
            "schema_version": "context-bundle/v1",
            "project": "demo",
            "repositories": [{"name": "demo", "relative_path": "projects/demo"}],
        }

        result = submit_task(
            f"http://127.0.0.1:{server.server_port}",
            envelope=envelope,
            bundle=bundle,
            receipt=receipt,
        )
    finally:
        server.shutdown()
        thread.join()
        server.server_close()

    assert result.completed is True
    assert result.snapshot_id == "snapshot-1"
    assert [path for path, _ in requests] == [
        "/api/harness/context-snapshots",
        "/api/harness/tasks",
        "/api/harness/context-receipts",
        "/api/harness/tasks/task-1/activate",
    ]
    assert requests[1][1]["task_id"] == "task-1"
    assert requests[2][1]["status"] == "delivered"
