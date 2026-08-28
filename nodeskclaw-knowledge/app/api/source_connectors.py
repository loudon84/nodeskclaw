"""Source connector API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_member_context, get_runtime_adapter
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.schemas.common import ApiResponse, PageData
from app.schemas.connector import (
    ConnectorCreate,
    ConnectorCredentialPut,
    ConnectorOut,
    ConnectorSourceObjectOut,
    ConnectorSyncCreate,
    ConnectorSyncRunOut,
    ConnectorUpdate,
)
from app.schemas.principal import KnowledgePrincipal
from app.services import connector_service

router = APIRouter(tags=["source-connectors"])
kb_connectors_router = APIRouter(prefix="/knowledge-bases", tags=["source-connectors"])


async def _to_out(db: AsyncSession, row) -> ConnectorOut:
    extra = await connector_service.connector_out_extra(db, row)
    data = ConnectorOut.model_validate(row).model_dump()
    data.update(extra)
    return ConnectorOut.model_validate(data)


@router.get("/source-connectors/types", response_model=ApiResponse)
async def list_types(member: KnowledgePrincipal = Depends(get_member_context)):
    del member
    return ApiResponse(data=await connector_service.list_connector_types())


@router.get("/source-connectors", response_model=ApiResponse[PageData[ConnectorOut]])
async def list_connectors(
    knowledge_base_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await connector_service.list_connectors(
        db, member, knowledge_base_id=knowledge_base_id, page=page, page_size=page_size
    )
    outs = [await _to_out(db, i) for i in items]
    return ApiResponse(data=PageData(items=outs, total=total, page=page, page_size=page_size))


@kb_connectors_router.post("/{kb_id}/source-connectors", response_model=ApiResponse[ConnectorOut])
async def create_connector(
    kb_id: str,
    body: ConnectorCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await connector_service.create_connector(
        db,
        member,
        knowledge_base_id=kb_id,
        name=body.name,
        connector_type=body.connector_type,
        config=body.config,
        sync_mode=body.sync_mode,
        sync_interval_seconds=body.sync_interval_seconds,
    )
    return ApiResponse(data=await _to_out(db, row))


@router.get("/source-connectors/{connector_id}", response_model=ApiResponse[ConnectorOut])
async def get_connector(
    connector_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await connector_service.get_connector(db, member, connector_id)
    return ApiResponse(data=await _to_out(db, row))


@router.patch("/source-connectors/{connector_id}", response_model=ApiResponse[ConnectorOut])
async def update_connector(
    connector_id: str,
    body: ConnectorUpdate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await connector_service.update_connector(
        db,
        member,
        connector_id,
        name=body.name,
        config=body.config,
        sync_mode=body.sync_mode,
        sync_interval_seconds=body.sync_interval_seconds,
        status=body.status,
    )
    return ApiResponse(data=await _to_out(db, row))


@router.delete("/source-connectors/{connector_id}", response_model=ApiResponse)
async def delete_connector(
    connector_id: str,
    policy: str = Query("archive_sources"),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    await connector_service.delete_connector(db, member, ragflow, connector_id, policy=policy)
    return ApiResponse(message="deleted")


@router.post("/source-connectors/{connector_id}/test", response_model=ApiResponse)
async def test_connector(
    connector_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    data = await connector_service.test_connector(db, member, connector_id)
    return ApiResponse(data=data)


@router.post("/source-connectors/{connector_id}/pause", response_model=ApiResponse[ConnectorOut])
async def pause_connector(
    connector_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await connector_service.pause_connector(db, member, connector_id)
    return ApiResponse(data=await _to_out(db, row))


@router.post("/source-connectors/{connector_id}/resume", response_model=ApiResponse[ConnectorOut])
async def resume_connector(
    connector_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await connector_service.resume_connector(db, member, connector_id)
    return ApiResponse(data=await _to_out(db, row))


@router.post("/source-connectors/{connector_id}/sync", response_model=ApiResponse[ConnectorSyncRunOut], status_code=202)
async def sync_connector(
    connector_id: str,
    body: ConnectorSyncCreate | None = None,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    trigger = (body.trigger if body else None) or "manual"
    run = await connector_service.trigger_sync(db, member, connector_id, trigger=trigger)
    return ApiResponse(data=ConnectorSyncRunOut.model_validate(run))


@router.put("/source-connectors/{connector_id}/credential", response_model=ApiResponse[ConnectorOut])
async def put_credential(
    connector_id: str,
    body: ConnectorCredentialPut,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await connector_service.put_credential(db, member, connector_id, body.payload)
    return ApiResponse(data=await _to_out(db, row))


@router.delete("/source-connectors/{connector_id}/credential", response_model=ApiResponse)
async def delete_credential(
    connector_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    await connector_service.delete_credential(db, member, connector_id)
    return ApiResponse(message="deleted")


@router.get("/source-connectors/{connector_id}/sync-runs", response_model=ApiResponse[PageData[ConnectorSyncRunOut]])
async def list_sync_runs(
    connector_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await connector_service.list_sync_runs(db, member, connector_id, page=page, page_size=page_size)
    return ApiResponse(
        data=PageData(
            items=[ConnectorSyncRunOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/source-connectors/{connector_id}/sync-runs/{run_id}", response_model=ApiResponse[ConnectorSyncRunOut])
async def get_sync_run(
    connector_id: str,
    run_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    run = await connector_service.get_sync_run(db, member, connector_id, run_id)
    return ApiResponse(data=ConnectorSyncRunOut.model_validate(run))


@router.post(
    "/source-connectors/{connector_id}/sync-runs/{run_id}/retry",
    response_model=ApiResponse[ConnectorSyncRunOut],
    status_code=202,
)
async def retry_sync_run(
    connector_id: str,
    run_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    run = await connector_service.retry_sync_run(db, member, connector_id, run_id)
    return ApiResponse(data=ConnectorSyncRunOut.model_validate(run))


@router.post(
    "/source-connectors/{connector_id}/sync-runs/{run_id}/cancel",
    response_model=ApiResponse[ConnectorSyncRunOut],
)
async def cancel_sync_run(
    connector_id: str,
    run_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    run = await connector_service.cancel_sync_run(db, member, connector_id, run_id)
    return ApiResponse(data=ConnectorSyncRunOut.model_validate(run))


@router.get(
    "/source-connectors/{connector_id}/objects",
    response_model=ApiResponse[PageData[ConnectorSourceObjectOut]],
)
async def list_objects(
    connector_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await connector_service.list_objects(db, member, connector_id, page=page, page_size=page_size)
    return ApiResponse(
        data=PageData(
            items=[ConnectorSourceObjectOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get(
    "/source-connectors/{connector_id}/objects/{object_id}",
    response_model=ApiResponse[ConnectorSourceObjectOut],
)
async def get_object(
    connector_id: str,
    object_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    obj = await connector_service.get_object(db, member, connector_id, object_id)
    return ApiResponse(data=ConnectorSourceObjectOut.model_validate(obj))
