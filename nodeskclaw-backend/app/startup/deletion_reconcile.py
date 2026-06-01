"""恢复卡在 deleting 状态的实例删除任务。"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.instance import Instance, InstanceStatus
from app.services.instance_service import schedule_instance_deletion_finalizer

logger = logging.getLogger(__name__)


async def resume_deleting_instances(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    async with session_factory() as db:
        result = await db.execute(
            select(Instance.id, Instance.name).where(
                Instance.status == InstanceStatus.deleting,
                Instance.deleted_at.is_(None),
            )
        )
        rows = result.all()

    for instance_id, name in rows:
        schedule_instance_deletion_finalizer(instance_id)
        logger.info("已恢复实例删除任务: %s (%s)", name, instance_id)

    if rows:
        logger.info("恢复 %d 个 deleting 实例删除任务", len(rows))
    return len(rows)
