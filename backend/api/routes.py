"""Loopback-only HTTP routes for local audit ingestion and review."""

import ipaddress
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from services.audit_service import AuditService
from services.harness_service import HarnessService


router = APIRouter()
harness_service = HarnessService()
audit_service = AuditService(run_resolver=harness_service.resolve_or_create_run)


def require_loopback(request: Request) -> None:
    host = request.client.host if request.client else ""
    try:
        is_loopback = ipaddress.ip_address(host).is_loopback
    except ValueError:
        is_loopback = False
    if not is_loopback:
        raise HTTPException(status_code=403, detail="audit routes require loopback access")


@router.post("/audit/events", status_code=201, dependencies=[Depends(require_loopback)])
async def ingest_audit_event(payload: dict[str, Any] = Body(...)):
    try:
        return audit_service.ingest(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/audit/sessions", dependencies=[Depends(require_loopback)])
async def list_audit_sessions():
    return audit_service.list_sessions()


@router.get("/audit/sessions/{session_id}", dependencies=[Depends(require_loopback)])
async def get_audit_session(session_id: str):
    session = audit_service.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="audit session not found")
    return session


@router.delete(
    "/audit/sessions/{session_id}",
    status_code=204,
    dependencies=[Depends(require_loopback)],
)
async def delete_audit_session(session_id: str):
    if not audit_service.delete_session(session_id):
        raise HTTPException(status_code=404, detail="audit session not found")
    return Response(status_code=204)


@router.get("/audit/stream", dependencies=[Depends(require_loopback)])
async def stream_audit_events(session_id: str | None = None):
    return StreamingResponse(
        audit_service.stream(session_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/harness/context-snapshots", status_code=201, dependencies=[Depends(require_loopback)])
async def import_context_snapshot(payload: dict[str, Any] = Body(...)):
    try:
        return harness_service.import_context_snapshot(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/harness/tasks", status_code=201, dependencies=[Depends(require_loopback)])
async def create_harness_task(payload: dict[str, Any] = Body(...)):
    try:
        return harness_service.create_task(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/harness/tasks", dependencies=[Depends(require_loopback)])
async def list_harness_tasks():
    return harness_service.list_tasks()


@router.get("/harness/tasks/{task_id}", dependencies=[Depends(require_loopback)])
async def get_harness_task(task_id: str):
    task = harness_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task


@router.post("/harness/context-receipts", status_code=201, dependencies=[Depends(require_loopback)])
async def ingest_context_receipt(payload: dict[str, Any] = Body(...)):
    try:
        return harness_service.ingest_context_receipt(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/harness/tasks/{task_id}/context-receipts", dependencies=[Depends(require_loopback)])
async def list_context_receipts(task_id: str):
    try:
        return harness_service.list_context_receipts(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/harness/tasks/{task_id}/activate", dependencies=[Depends(require_loopback)])
async def activate_harness_task(task_id: str, payload: dict[str, Any] = Body(...)):
    try:
        return harness_service.activate_task(task_id, str(payload.get("repository_path", "")))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/harness/runs/unbound", dependencies=[Depends(require_loopback)])
async def list_unbound_runs():
    return harness_service.list_unbound_runs()
