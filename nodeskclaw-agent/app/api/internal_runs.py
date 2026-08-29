import base64
import hashlib
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_internal_token
from app.db import get_db
from app.schemas import (
    ArtifactDescriptor,
    ArtifactUploadRequest,
    ArtifactsResponse,
    CreateRunRequest,
    CreateRunResponse,
    EventsResponse,
    MutationResponse,
    ResultResponse,
    RunView,
)
from app.services import run_service

router = APIRouter(prefix="/internal/v1", tags=["internal-runs"])


@router.post("/runs", response_model=CreateRunResponse, dependencies=[Depends(require_internal_token)])
async def create_internal_run(
    body: CreateRunRequest,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str = Header(alias="X-Exec-Org-Id"),
    x_exec_user_id: str = Header(alias="X-Exec-User-Id"),
) -> CreateRunResponse:
    if not x_exec_org_id or not x_exec_user_id:
        raise HTTPException(status_code=400, detail="missing execution context headers")
    if body.org_id and body.org_id != x_exec_org_id:
        raise HTTPException(status_code=403, detail="forged org_id rejected")
    if body.user_id and body.user_id != x_exec_user_id:
        raise HTTPException(status_code=403, detail="forged user_id rejected")
    return await run_service.create_run(
        db,
        body,
        org_id=x_exec_org_id,
        user_id=x_exec_user_id,
    )


@router.get("/runs/{run_id}", response_model=RunView, dependencies=[Depends(require_internal_token)])
async def get_internal_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str = Header(alias="X-Exec-Org-Id"),
) -> RunView:
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/runs/{run_id}/events", response_model=EventsResponse, dependencies=[Depends(require_internal_token)])
async def get_internal_events(
    run_id: str,
    after_seq: int = 0,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str = Header(alias="X-Exec-Org-Id"),
) -> EventsResponse:
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    items = await run_service.list_events(db, run_id, after_seq=after_seq)
    next_seq = items[-1].event_seq if items else (after_seq if after_seq > 0 else 0)
    return EventsResponse(
        org_id=run.org_id,
        run_id=run.run_id,
        items=items,
        next_seq=next_seq,
    )


@router.get("/runs/{run_id}/result", response_model=ResultResponse, dependencies=[Depends(require_internal_token)])
async def get_internal_result(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str = Header(alias="X-Exec-Org-Id"),
) -> ResultResponse:
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return ResultResponse(
        org_id=run.org_id,
        run_id=run.run_id,
        status=run.status,
        result=run.result,
    )


@router.get("/runs/{run_id}/artifacts", response_model=ArtifactsResponse, dependencies=[Depends(require_internal_token)])
async def get_internal_artifacts(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str = Header(alias="X-Exec-Org-Id"),
) -> ArtifactsResponse:
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    items = await run_service.list_artifacts(db, run_id)
    return ArtifactsResponse(
        org_id=run.org_id,
        run_id=run.run_id,
        items=items,
    )


def _artifact_error_response(status_code: int, error_code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error_code": error_code,
            "message_key": error_code,
            "message": message,
            "detail": message,
        },
    )


@router.post("/runs/{run_id}/artifacts", response_model=ArtifactDescriptor, dependencies=[Depends(require_internal_token)])
async def upload_internal_artifact(
    run_id: str,
    body: ArtifactUploadRequest,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str = Header(alias="X-Exec-Org-Id"),
):
    if not x_exec_org_id:
        return _artifact_error_response(400, "errors.artifact.missing_field", "X-Exec-Org-Id header is required")

    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    if run.org_id != x_exec_org_id:
        return _artifact_error_response(403, "errors.artifact.unauthorized_scope", "org_id scope mismatch")

    if not body.name or not body.content_base64:
        return _artifact_error_response(400, "errors.artifact.missing_field", "name and content_base64 are required")

    if body.generation is not None and body.generation != run.generation:
        return _artifact_error_response(409, "errors.artifact.stale_generation", f"generation mismatch: expected {run.generation}, got {body.generation}")

    if body.attempt_id and run.attempt_id and body.attempt_id != run.attempt_id:
        return _artifact_error_response(403, "errors.artifact.unauthorized_scope", f"attempt_id mismatch: expected {run.attempt_id}, got {body.attempt_id}")

    try:
        content_bytes = base64.b64decode(body.content_base64)
    except Exception:
        return _artifact_error_response(400, "errors.artifact.missing_field", "invalid base64 content")

    if body.size is not None and body.size != len(content_bytes):
        return _artifact_error_response(400, "errors.artifact.size_mismatch", f"size mismatch: expected {body.size}, got {len(content_bytes)}")

    actual_checksum = hashlib.sha256(content_bytes).hexdigest()
    if body.checksum_sha256 and actual_checksum.lower() != body.checksum_sha256.lower():
        return _artifact_error_response(400, "errors.artifact.checksum_mismatch", f"checksum mismatch: expected {body.checksum_sha256}, got {actual_checksum}")

    try:
        descriptor = await run_service.store_artifact_bytes(
            db,
            run_id,
            name=body.name,
            content=content_bytes,
            content_type=body.content_type,
            org_id=x_exec_org_id,
            attempt_id=body.attempt_id,
            generation=body.generation,
            step_id=body.step_id,
            upload_mode=body.upload_mode,
            idempotency_key=body.idempotency_key,
        )
        await db.commit()
        return descriptor
    except RuntimeError as exc:
        err_msg = str(exc)
        if "idempotency_conflict" in err_msg or err_msg == "errors.artifact.idempotency_conflict":
            return _artifact_error_response(409, "errors.artifact.idempotency_conflict", "artifact idempotency conflict: checksum or name mismatch")
        return _artifact_error_response(409, "errors.artifact.idempotency_conflict", err_msg)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/runs/{run_id}/artifacts/{artifact_id}/bytes", dependencies=[Depends(require_internal_token)])
async def get_internal_artifact_bytes(
    run_id: str,
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str = Header(alias="X-Exec-Org-Id"),
):
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    packed = await run_service.get_artifact_bytes(db, run_id, artifact_id)
    if not packed:
        raise HTTPException(status_code=404, detail="artifact not found")
    meta, content = packed
    filename = meta.get("name") or artifact_id
    encoded_filename = quote(filename)
    return Response(
        content=content,
        media_type=meta.get("content_type") or "application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}",
            "X-Checksum-SHA256": meta.get("checksum_sha256") or "",
        },
    )


@router.post("/runs/{run_id}/events/ingest", dependencies=[Depends(require_internal_token)])
async def ingest_internal_events(
    run_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str = Header(alias="X-Exec-Org-Id"),
):
    body_org_id = body.get("org_id")
    if body_org_id and body_org_id != x_exec_org_id:
        raise HTTPException(status_code=403, detail="forged org_id rejected")
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    events = body.get("events") or []
    valid_count = 0

    try:
        steps_res = await db.execute(
            text(f'SELECT step_id, status, run_generation, attempt_id FROM "{run_service.SCHEMA}".run_steps WHERE run_id = :run_id'),
            {"run_id": run_id},
        )
        steps_rows = steps_res.mappings().all() if hasattr(steps_res, "mappings") else []
    except Exception:
        steps_rows = []
    valid_step_ids = {s["step_id"] for s in steps_rows}

    for event in events:
        event_type = str(event.get("event_type") or "run.progress")
        payload = event.get("payload") or {}
        source = str(event.get("source") or "edge")
        source_event_id = event.get("source_event_id") or event.get("event_id")
        step_id = event.get("step_id") or payload.get("step_id")
        event_attempt_id = event.get("attempt_id") or payload.get("attempt_id")
        event_run_gen = event.get("run_generation") or payload.get("run_generation")

        # 1. Step id validation if steps exist
        if valid_step_ids and step_id and step_id not in valid_step_ids:
            await run_service.record_event_rejection(
                db,
                run_id,
                reason="invalid_step_id",
                event_id=event.get("event_id"),
                source_event_id=source_event_id,
                details={"step_id": step_id, "event_type": event_type},
            )
            continue

        # 2. Attempt / generation validation
        if event_attempt_id and run.attempt_id and str(event_attempt_id) != str(run.attempt_id):
            await run_service.record_event_rejection(
                db,
                run_id,
                reason="old_attempt",
                event_id=event.get("event_id"),
                source_event_id=source_event_id,
                details={"event_attempt_id": event_attempt_id, "run_attempt_id": run.attempt_id},
            )
            continue

        if event_run_gen is not None and run.generation is not None and int(event_run_gen) != int(run.generation):
            await run_service.record_event_rejection(
                db,
                run_id,
                reason="old_generation",
                event_id=event.get("event_id"),
                source_event_id=source_event_id,
                details={"event_run_generation": event_run_gen, "run_generation": run.generation},
            )
            continue

        # 3. Append event
        try:
            await run_service.append_event(
                db,
                run_id,
                event_type,
                payload,
                org_id=x_exec_org_id,
                attempt_id=run.attempt_id,
                generation=run.generation,
                source=source,
                source_event_id=source_event_id,
            )
        except RuntimeError as err:
            if "idempotency conflict" in str(err) or "stale attempt" in str(err):
                await run_service.record_event_rejection(
                    db,
                    run_id,
                    reason="duplicate_event_id" if "idempotency" in str(err) else "old_attempt",
                    event_id=event.get("event_id"),
                    source_event_id=source_event_id,
                    details={"error": str(err)},
                )
                continue
            raise

        valid_count += 1

        # 4. Update step state and trigger aggregator on step terminal events
        if step_id and step_id in valid_step_ids:
            if event_type in ("run.completed", "step.completed", "edge.job.completed"):
                await run_service.update_step_state(
                    db,
                    run_id,
                    step_id,
                    "SUCCEEDED",
                    result=payload,
                )
                await run_service.aggregate_run_terminal(db, run_id, org_id=x_exec_org_id)
            elif event_type in ("run.failed", "step.failed", "edge.job.failed"):
                await run_service.update_step_state(
                    db,
                    run_id,
                    step_id,
                    "FAILED",
                    error_message=str(payload.get("error") or "step failed"),
                )
                await run_service.aggregate_run_terminal(db, run_id, org_id=x_exec_org_id)
            elif event_type in ("run.cancelled", "step.cancelled", "edge.job.cancelled"):
                await run_service.update_step_state(
                    db,
                    run_id,
                    step_id,
                    "CANCELLED",
                )
                await run_service.aggregate_run_terminal(db, run_id, org_id=x_exec_org_id)
            else:
                await run_service.update_step_state(
                    db,
                    run_id,
                    step_id,
                    "RUNNING",
                    expected_status=["PENDING", "READY", "DISPATCHED"],
                )

    await db.commit()
    return {"ok": True, "count": valid_count, "org_id": run.org_id, "run_id": run.run_id}


@router.post("/runs/{run_id}/cancel", response_model=MutationResponse, dependencies=[Depends(require_internal_token)])
async def cancel_internal_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str = Header(alias="X-Exec-Org-Id"),
) -> MutationResponse:
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    cancelled = await run_service.cancel_run(db, run_id, org_id=x_exec_org_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="run not found")
    return MutationResponse(
        org_id=cancelled.org_id,
        run_id=cancelled.run_id,
        status=cancelled.status,
        idempotent=True,
    )


@router.post("/runs/{run_id}/resume", response_model=MutationResponse, dependencies=[Depends(require_internal_token)])
async def resume_internal_run(
    run_id: str,
    body: dict | None = None,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str = Header(alias="X-Exec-Org-Id"),
) -> MutationResponse:
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status == "WAITING_APPROVAL":
        raise HTTPException(status_code=400, detail="run in WAITING_APPROVAL state requires approval, not resume")
    evidence = body.get("evidence") if body else None
    try:
        res = await run_service.resume_run(db, run_id, evidence=evidence, org_id=x_exec_org_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not res:
        raise HTTPException(status_code=404, detail="run not found")
    return MutationResponse(
        org_id=res.org_id,
        run_id=res.run_id,
        status=res.status,
        idempotent=True,
    )


@router.post("/runs/{run_id}/approvals/{approval_id}", response_model=MutationResponse, dependencies=[Depends(require_internal_token)])
async def approve_internal_run(
    run_id: str,
    approval_id: str,
    body: dict | None = None,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str = Header(alias="X-Exec-Org-Id"),
) -> MutationResponse:
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    evidence = body.get("evidence") if body else None
    res = await run_service.approve_run(db, run_id, approval_id=approval_id, evidence=evidence, org_id=x_exec_org_id)
    if not res:
        raise HTTPException(status_code=404, detail="run not found")
    return MutationResponse(
        org_id=res.org_id,
        run_id=res.run_id,
        status=res.status,
        idempotent=True,
    )
