from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.user_cache import UserCache
from app.schemas.common import ApiResponse
from app.schemas.resource import RpaWorkerResponse
from app.services import rpa_worker_service

router = APIRouter()


def _to_worker_response(worker) -> RpaWorkerResponse:
    return RpaWorkerResponse(
        id=worker.worker_id,
        worker_type=worker.worker_type,
        device_name=worker.device_name,
        user_id=worker.user_id,
        status=worker.status,
        capabilities=rpa_worker_service.worker_capabilities(worker),
        app_version=worker.app_version,
        agent_version=worker.agent_version,
        os=worker.os,
        current_run_id=worker.current_run_id,
        last_heartbeat_at=worker.last_heartbeat_at,
    )


@router.get("", response_model=ApiResponse[list[RpaWorkerResponse]])
async def list_workers(
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    workers = await rpa_worker_service.list_workers(db)
    return ApiResponse(data=[_to_worker_response(w) for w in workers])


@router.get("/{worker_id}", response_model=ApiResponse[RpaWorkerResponse])
async def get_worker(
    worker_id: str,
    db: AsyncSession = Depends(get_db),
    user: UserCache = Depends(get_current_user),
):
    worker = await rpa_worker_service.get_worker(db, worker_id)
    return ApiResponse(data=_to_worker_response(worker))
