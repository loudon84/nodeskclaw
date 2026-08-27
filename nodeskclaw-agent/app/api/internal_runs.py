from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_internal_token
from app.db import get_db
from app.schemas import CreateRunRequest, CreateRunResponse
from app.services import run_service

router = APIRouter(prefix="/internal/v1", tags=["internal-runs"])


@router.post("/runs", response_model=CreateRunResponse, dependencies=[Depends(require_internal_token)])
async def create_internal_run(
    body: CreateRunRequest,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
    x_exec_user_id: str | None = Header(default=None, alias="X-Exec-User-Id"),
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


@router.get("/runs/{run_id}", dependencies=[Depends(require_internal_token)])
async def get_internal_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
):
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/runs/{run_id}/events", dependencies=[Depends(require_internal_token)])
async def get_internal_events(
    run_id: str,
    after_seq: int = 0,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
):
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "org_id": run.org_id,
        "run_id": run.run_id,
        "items": await run_service.list_events(db, run_id, after_seq=after_seq),
    }


@router.get("/runs/{run_id}/result", dependencies=[Depends(require_internal_token)])
async def get_internal_result(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
):
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {"org_id": run.org_id, "run_id": run.run_id, "status": run.status, "result": run.result}


@router.get("/runs/{run_id}/artifacts", dependencies=[Depends(require_internal_token)])
async def get_internal_artifacts(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
):
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    return {"org_id": run.org_id, "run_id": run.run_id, "items": await run_service.list_artifacts(db, run_id)}


@router.get("/runs/{run_id}/artifacts/{artifact_id}/bytes", dependencies=[Depends(require_internal_token)])
async def get_internal_artifact_bytes(
    run_id: str,
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
):
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    packed = await run_service.get_artifact_bytes(db, run_id, artifact_id)
    if not packed:
        raise HTTPException(status_code=404, detail="artifact not found")
    meta, content = packed
    from urllib.parse import quote
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
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
):
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
            await run_service.set_status(db, run_id, "COMPLETED", result=payload)
        elif event_type == "run.failed":
            await run_service.set_status(db, run_id, "FAILED", result=payload)
        await run_service.append_event(
            db,
            run_id,
            event_type,
            payload,
            source=source,
            source_event_id=source_event_id,
        )
    await db.commit()
    return {"ok": True, "count": len(events)}


@router.post("/runs/{run_id}/cancel", dependencies=[Depends(require_internal_token)])
async def cancel_internal_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
):
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    cancelled = await run_service.cancel_run(db, run_id)
    return cancelled


@router.post("/runs/{run_id}/resume", dependencies=[Depends(require_internal_token)])
@router.post("/runs/{run_id}/approvals/{approval_id}", dependencies=[Depends(require_internal_token)])
async def approve_internal_run(
    run_id: str,
    body: dict | None = None,
    db: AsyncSession = Depends(get_db),
    approval_id: str | None = None,
    x_exec_org_id: str | None = Header(default=None, alias="X-Exec-Org-Id"),
):
    run = await run_service.get_run(db, run_id, org_id=x_exec_org_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    evidence = body.get("evidence") if body else None
    res = await run_service.approve_run(db, run_id, approval_id=approval_id, evidence=evidence)
    return res
