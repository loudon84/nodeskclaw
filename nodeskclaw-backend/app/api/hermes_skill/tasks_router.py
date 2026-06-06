import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.core.exceptions import NotFoundError
from app.schemas.hermes_skill.task import TaskRead
from app.schemas.hermes_skill.artifact import ArtifactRead
from app.services.hermes_skill.task_service import TaskService
from app.services.hermes_skill.task_event_service import TaskEventService
from app.services.hermes_skill.artifact_service import ArtifactService
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:view")
    service = TaskService(db)
    task = await service.get_task(task_id, org.id)
    return _ok(TaskRead.model_validate(task).model_dump())


@router.get("/tasks/{task_id}/events")
async def stream_task_events(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:view")
    service = TaskService(db)
    await service.get_task(task_id, org.id)

    event_service = TaskEventService(db)

    async def _event_generator():
        async for event in event_service.stream_events(task_id, org.id):
            if event is None:
                yield f": heartbeat\n\n"
            else:
                data = json.dumps({
                    "event_type": event.event_type.value,
                    "event_seq": event.event_seq,
                    "payload": event.payload,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                })
                yield f"data: {data}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tasks/{task_id}/artifacts")
async def list_task_artifacts(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:view")
    service = ArtifactService(db)
    artifacts, _ = await service.list_artifacts(org_id=org.id, task_id=task_id, user_id=user.id if user else None)
    items = [ArtifactRead.model_validate(a).model_dump() for a in artifacts]
    return _ok(items)
