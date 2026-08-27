from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_internal_token
from app.db import get_db
from app.schemas import (
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
    for event in events:
        event_type = str(event.get("event_type") or "run.progress")
        payload = event.get("payload") or {}
        source = str(event.get("source") or "edge")
        source_event_id = event.get("source_event_id") or event.get("event_id")
        if event_type == "run.completed":
            await run_service.set_status(
                db,
                run_id,
                "COMPLETED",
                org_id=x_exec_org_id,
                attempt_id=run.attempt_id,
                generation=run.generation,
                expected_status=["RUNNING", "PREPARING", "RESUMING", "WAITING_EDGE"],
                result=payload,
            )
        elif event_type == "run.failed":
            await run_service.set_status(
                db,
                run_id,
                "FAILED",
                org_id=x_exec_org_id,
                attempt_id=run.attempt_id,
                generation=run.generation,
                expected_status=["RUNNING", "PREPARING", "RESUMING", "WAITING_EDGE"],
                result=payload,
            )
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
    await db.commit()
    return {"ok": True, "count": len(events), "org_id": run.org_id, "run_id": run.run_id}


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
