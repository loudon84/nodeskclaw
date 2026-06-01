"""Global agent performance API — cross-workspace aggregated payslip."""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, select as sa_select, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.models.instance import Instance
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_task import WorkspaceTask

logger = logging.getLogger(__name__)
router = APIRouter()


def _ok(data=None, message: str = "success"):
    return {"code": 0, "message": message, "data": data}


def _get_current_user_dep():
    from app.core.security import get_current_user
    return get_current_user


@router.get("/users/me/agent-performance")
async def get_global_agent_performance(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user=Depends(_get_current_user_dep()),
):
    """Aggregated AI employee performance across all workspaces the user belongs to."""
    from app.schemas.workspace import (
        GlobalAgentMetrics,
        GlobalAgentPerformanceResponse,
        WorkspaceBreakdown,
    )

    ws_q = sa_select(WorkspaceMember.workspace_id).where(
        WorkspaceMember.user_id == user.id,
        WorkspaceMember.deleted_at.is_(None),
    )
    ws_ids = (await db.execute(ws_q)).scalars().all()
    if not ws_ids:
        return _ok(GlobalAgentPerformanceResponse(agents=[]).model_dump())

    cutoff = func.now() - func.make_interval(0, 0, 0, days)

    completed_case = case(
        (WorkspaceTask.status.in_(["done", "archived"]), 1), else_=0
    )
    failed_case = case((WorkspaceTask.status == "failed", 1), else_=0)

    has_duration = (
        WorkspaceTask.started_at.isnot(None)
        & WorkspaceTask.completed_at.isnot(None)
        & WorkspaceTask.status.in_(["done", "archived"])
    )
    duration_expr = extract("epoch", WorkspaceTask.completed_at - WorkspaceTask.started_at) / 60

    global_q = (
        sa_select(
            WorkspaceTask.assignee_instance_id,
            func.count().label("total"),
            func.sum(completed_case).label("completed"),
            func.sum(failed_case).label("failed"),
            func.sum(case((has_duration, duration_expr), else_=None)).label("total_work_min"),
            func.avg(case((has_duration, duration_expr), else_=None)).label("avg_duration_min"),
            func.coalesce(func.sum(WorkspaceTask.token_cost), 0).label("total_token_cost"),
            func.coalesce(func.sum(WorkspaceTask.prompt_token_cost), 0).label("total_prompt_token_cost"),
            func.coalesce(func.sum(WorkspaceTask.completion_token_cost), 0).label("total_completion_token_cost"),
            func.coalesce(func.sum(WorkspaceTask.estimated_value), 0).label("total_estimated_value"),
            func.coalesce(func.sum(WorkspaceTask.actual_value), 0).label("total_actual_value"),
        )
        .where(
            WorkspaceTask.workspace_id.in_(ws_ids),
            WorkspaceTask.deleted_at.is_(None),
            WorkspaceTask.assignee_instance_id.isnot(None),
            WorkspaceTask.created_at >= cutoff,
        )
        .group_by(WorkspaceTask.assignee_instance_id)
    )
    global_rows = (await db.execute(global_q)).all()

    if not global_rows:
        return _ok(GlobalAgentPerformanceResponse(agents=[]).model_dump())

    instance_ids = [r.assignee_instance_id for r in global_rows]

    ws_q2 = (
        sa_select(
            WorkspaceTask.assignee_instance_id,
            WorkspaceTask.workspace_id,
            Workspace.name.label("workspace_name"),
            func.count().label("total"),
            func.sum(completed_case).label("completed"),
            func.sum(failed_case).label("failed"),
            func.coalesce(func.sum(WorkspaceTask.token_cost), 0).label("total_token_cost"),
            func.coalesce(func.sum(WorkspaceTask.actual_value), 0).label("total_actual_value"),
        )
        .join(Workspace, Workspace.id == WorkspaceTask.workspace_id)
        .where(
            WorkspaceTask.workspace_id.in_(ws_ids),
            WorkspaceTask.deleted_at.is_(None),
            WorkspaceTask.assignee_instance_id.isnot(None),
            WorkspaceTask.created_at >= cutoff,
        )
        .group_by(
            WorkspaceTask.assignee_instance_id,
            WorkspaceTask.workspace_id,
            Workspace.name,
        )
    )
    ws_rows = (await db.execute(ws_q2)).all()

    ws_breakdown_map: dict[str, list[WorkspaceBreakdown]] = {}
    for r in ws_rows:
        comp = int(r.completed)
        fail = int(r.failed)
        denom = comp + fail
        ws_breakdown_map.setdefault(r.assignee_instance_id, []).append(
            WorkspaceBreakdown(
                workspace_id=r.workspace_id,
                workspace_name=r.workspace_name,
                total_tasks=int(r.total),
                completed_tasks=comp,
                success_rate=round(comp / denom, 4) if denom > 0 else None,
                total_token_cost=int(r.total_token_cost),
                total_actual_value=round(float(r.total_actual_value), 2),
            )
        )

    name_q = (
        sa_select(
            Instance.id,
            func.coalesce(Instance.agent_display_name, Instance.name).label("name"),
        )
        .where(Instance.id.in_(instance_ids), Instance.deleted_at.is_(None))
    )
    name_rows = (await db.execute(name_q)).all()
    name_map = {r.id: r.name for r in name_rows}

    agents = []
    for r in global_rows:
        iid = r.assignee_instance_id
        comp = int(r.completed)
        fail = int(r.failed)
        denom = comp + fail
        total_tok = int(r.total_token_cost)
        total_actual = float(r.total_actual_value)
        ws_list = ws_breakdown_map.get(iid, [])

        agents.append(GlobalAgentMetrics(
            instance_id=iid,
            agent_name=name_map.get(iid, iid),
            theme_color=None,
            total_tasks=int(r.total),
            completed_tasks=comp,
            failed_tasks=fail,
            success_rate=round(comp / denom, 4) if denom > 0 else None,
            total_work_minutes=round(float(r.total_work_min), 1) if r.total_work_min else None,
            avg_duration_minutes=round(float(r.avg_duration_min), 1) if r.avg_duration_min else None,
            total_token_cost=total_tok,
            total_prompt_token_cost=int(r.total_prompt_token_cost),
            total_completion_token_cost=int(r.total_completion_token_cost),
            total_estimated_value=round(float(r.total_estimated_value), 2),
            total_actual_value=round(total_actual, 2),
            roi_per_1k_tokens=round(total_actual / (total_tok / 1000), 4) if total_tok > 0 else None,
            workspace_count=len(ws_list),
            workspaces=ws_list,
        ))

    agents.sort(key=lambda a: a.total_tasks, reverse=True)
    return _ok(GlobalAgentPerformanceResponse(agents=agents).model_dump())
