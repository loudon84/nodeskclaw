"""Human action lifecycle."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import HumanActionStatus, TaskStatus
from app.models.human_action import HumanAction
from app.models.rpa_run import RpaRun
from app.models.user_cache import UserCache
from app.services.json_utils import dumps_json
from app.services.task_state_machine import transition


async def create_human_action_for_run(
    db: AsyncSession,
    *,
    task: AutomationTask,
    run: RpaRun | None,
    action_type: str,
    title: str,
    instruction: str,
    target_url: str | None = None,
    payload: dict | None = None,
) -> HumanAction:
    action = HumanAction(
        task_id=task.id,
        run_id=run.id if run else None,
        type=action_type,
        status=HumanActionStatus.PENDING,
        title=title,
        instruction=instruction,
        target_url=target_url,
        payload=dumps_json(payload or {}),
    )
    db.add(action)
    await db.flush()
    return action


async def list_pending_human_actions(db: AsyncSession, tenant_id: str) -> list[HumanAction]:
    result = await db.execute(
        select(HumanAction)
        .join(AutomationTask, HumanAction.task_id == AutomationTask.id)
        .where(
            AutomationTask.tenant_id == tenant_id,
            HumanAction.status == HumanActionStatus.PENDING,
            not_deleted(HumanAction),
            not_deleted(AutomationTask),
        )
        .order_by(HumanAction.created_at.asc())
    )
    return list(result.scalars().all())


async def get_human_action(db: AsyncSession, tenant_id: str, action_id: str) -> HumanAction:
    action = (
        await db.execute(
            select(HumanAction)
            .join(AutomationTask, HumanAction.task_id == AutomationTask.id)
            .where(
                HumanAction.id == action_id,
                AutomationTask.tenant_id == tenant_id,
                not_deleted(HumanAction),
                not_deleted(AutomationTask),
            )
        )
    ).scalar_one_or_none()
    if action is None:
        raise NotFoundError(message="人工操作不存在", message_key="errors.autotask.human_action_not_found")
    return action


async def open_human_action(db: AsyncSession, tenant_id: str, action_id: str, user: UserCache) -> HumanAction:
    action = await get_human_action(db, tenant_id, action_id)
    if action.status != HumanActionStatus.PENDING:
        raise BadRequestError(message="人工操作状态不允许打开", message_key="errors.autotask.human_action_invalid_state")
    task = (
        await db.execute(select(AutomationTask).where(AutomationTask.id == action.task_id, not_deleted(AutomationTask)))
    ).scalar_one()
    action.status = HumanActionStatus.OPENED
    action.opened_by = user.user_id
    action.opened_at = datetime.now(UTC)
    transition(task, TaskStatus.HUMAN_OPERATING)
    await db.commit()
    await db.refresh(action)
    return action


async def confirm_human_action(
    db: AsyncSession,
    tenant_id: str,
    action_id: str,
    user: UserCache,
    resume_running: bool = False,
) -> HumanAction:
    action = await get_human_action(db, tenant_id, action_id)
    if action.status not in {HumanActionStatus.PENDING, HumanActionStatus.OPENED}:
        raise BadRequestError(message="人工操作状态不允许确认", message_key="errors.autotask.human_action_invalid_state")
    task = (
        await db.execute(select(AutomationTask).where(AutomationTask.id == action.task_id, not_deleted(AutomationTask)))
    ).scalar_one()
    action.status = HumanActionStatus.CONFIRMED
    action.confirmed_by = user.user_id
    action.confirmed_at = datetime.now(UTC)
    if resume_running:
        transition(task, TaskStatus.RUNNING)
        if action.run_id:
            run = (
                await db.execute(select(RpaRun).where(RpaRun.id == action.run_id, not_deleted(RpaRun)))
            ).scalar_one_or_none()
            if run:
                run.status = TaskStatus.RUNNING
    else:
        transition(task, TaskStatus.SUCCESS_MANUAL)
        task.progress = 100
    await db.commit()
    await db.refresh(action)
    return action


async def cancel_human_action(db: AsyncSession, tenant_id: str, action_id: str, user: UserCache) -> HumanAction:
    action = await get_human_action(db, tenant_id, action_id)
    if action.status in {HumanActionStatus.CONFIRMED, HumanActionStatus.CANCELLED}:
        raise BadRequestError(message="人工操作状态不允许取消", message_key="errors.autotask.human_action_invalid_state")
    task = (
        await db.execute(select(AutomationTask).where(AutomationTask.id == action.task_id, not_deleted(AutomationTask)))
    ).scalar_one()
    action.status = HumanActionStatus.CANCELLED
    transition(task, TaskStatus.FAILED)
    await db.commit()
    await db.refresh(action)
    return action
