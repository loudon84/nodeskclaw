"""Orchestrate workspace creation from internal template (multi-agent deploy)."""

from __future__ import annotations

import asyncio
from copy import deepcopy
import logging
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import async_session_factory
from app.models.blackboard import Blackboard
from app.models.cluster import Cluster
from app.models.deploy_record import DeployRecord, DeployStatus
from app.models.instance_mcp_server import InstanceMcpServer
from app.models.org_llm_key import OrgLlmKey
from app.models.user import User
from app.models.workspace import Workspace
from app.models.workspace_deploy import WorkspaceDeploy
from app.models.workspace_template import WorkspaceTemplate
from app.models.base import not_deleted
from app.schemas.deploy import DeployRequest
from app.schemas.llm import LlmConfigItem
from app.schemas.workspace import AddAgentRequest, WorkspaceCreate
from app.services import deploy_service, workspace_service
from app.services.codex_provider import normalize_selected_models
from app.services.gene_service import install_gene_prerestart
from app.services.k8s.event_bus import event_bus
from app.services.registry_service import list_image_tags

logger = logging.getLogger(__name__)

_WS_DEPLOY_CHANNEL = "workspace_deploy_progress"
_BLACKBOARD_COORD = (0, 0)


def _publish(deploy_id: str, event: str, data: dict[str, Any]) -> None:
    payload = {"workspace_deploy_id": deploy_id, "event": event, **data}
    event_bus.publish(_WS_DEPLOY_CHANNEL, payload)


async def _get_org_cluster(
    db: AsyncSession,
    cluster_id: str,
    org_id: str,
) -> Cluster | None:
    return (
        await db.execute(
            select(Cluster).where(
                Cluster.id == cluster_id,
                Cluster.org_id == org_id,
                Cluster.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def _org_has_llm_key(db: AsyncSession, org_id: str, provider: str) -> bool:
    r = await db.execute(
        select(OrgLlmKey.id).where(
            OrgLlmKey.org_id == org_id,
            OrgLlmKey.provider == provider,
            OrgLlmKey.is_active.is_(True),
            OrgLlmKey.deleted_at.is_(None),
        ).limit(1)
    )
    return r.scalar_one_or_none() is not None


async def _build_llm_configs(
    db: AsyncSession, org_id: str, llm_providers: list[dict],
) -> list[LlmConfigItem]:
    items: list[LlmConfigItem] = []
    for entry in llm_providers or []:
        prov = entry.get("provider") if isinstance(entry, dict) else None
        if not prov:
            continue
        ks = "org" if await _org_has_llm_key(db, org_id, prov) else "personal"
        models = entry.get("models") if isinstance(entry, dict) else None
        sm = normalize_selected_models(prov, models)
        items.append(LlmConfigItem(provider=prov, key_source=ks, selected_models=sm))
    return items


async def _resolve_image_version(db: AsyncSession, runtime: str) -> str:
    tags = await list_image_tags(db, runtime=runtime or "openclaw")
    if tags:
        return tags[0]["tag"]
    return "latest"


def _is_int_coord(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _coord_from_values(q: Any, r: Any) -> tuple[int, int] | None:
    if not _is_int_coord(q) or not _is_int_coord(r):
        return None
    return q, r


def _layout_issue(
    code: str,
    message: str,
    *,
    agent_index: int | None = None,
    hex_q: int | None = None,
    hex_r: int | None = None,
    conflict_with: str | None = None,
) -> dict[str, Any]:
    issue: dict[str, Any] = {"code": code, "message": message}
    if agent_index is not None:
        issue["agent_index"] = agent_index
    if hex_q is not None:
        issue["hex_q"] = hex_q
    if hex_r is not None:
        issue["hex_r"] = hex_r
    if conflict_with is not None:
        issue["conflict_with"] = conflict_with
    return issue


def _normalize_excluded_corridor_coords(
    excluded_corridor_coords: list[list[int]] | None,
) -> list[list[int]]:
    normalized: list[list[int]] = []
    seen: set[tuple[int, int]] = set()
    for coord in excluded_corridor_coords or []:
        if not isinstance(coord, list | tuple) or len(coord) < 2:
            continue
        parsed = _coord_from_values(coord[0], coord[1])
        if parsed is None or parsed in seen:
            continue
        seen.add(parsed)
        normalized.append([parsed[0], parsed[1]])
    return normalized


def _selected_agent_indices(agent_specs: list[dict], selected_agent_indices: list[int] | None) -> list[int]:
    if selected_agent_indices is None:
        return list(range(len(agent_specs)))
    seen: set[int] = set()
    valid: list[int] = []
    for idx in selected_agent_indices:
        if not isinstance(idx, int) or isinstance(idx, bool):
            continue
        if 0 <= idx < len(agent_specs) and idx not in seen:
            seen.add(idx)
            valid.append(idx)
    return sorted(valid)


def prepare_template_deploy_layout(
    template: WorkspaceTemplate,
    *,
    selected_agent_indices: list[int] | None = None,
    excluded_corridor_coords: list[list[int]] | None = None,
    agent_positions: list[dict[str, Any]] | None = None,
    require_explicit_agent_positions: bool = False,
) -> dict[str, Any]:
    agent_specs: list[dict] = list(template.agent_specs or [])
    selected_indices = _selected_agent_indices(agent_specs, selected_agent_indices)
    selected_set = set(selected_indices)
    excluded_corridors = _normalize_excluded_corridor_coords(excluded_corridor_coords)
    excluded_corridor_set = {(c[0], c[1]) for c in excluded_corridors}

    issues: list[dict[str, Any]] = []
    override_by_index: dict[int, dict[str, Any]] = {}
    for raw in agent_positions or []:
        if not isinstance(raw, dict):
            continue
        idx = raw.get("agent_index")
        if not isinstance(idx, int) or isinstance(idx, bool) or idx < 0 or idx >= len(agent_specs):
            issues.append(_layout_issue(
                "invalid_agent_index",
                "位置覆盖引用了不存在的 Agent",
            ))
            continue
        if idx not in selected_set:
            issues.append(_layout_issue(
                "unselected_position",
                "未选中的 Agent 不允许提交位置覆盖",
                agent_index=idx,
            ))
            continue
        override_by_index[idx] = raw

    reserved_coords: dict[tuple[int, int], str] = {_BLACKBOARD_COORD: "blackboard"}
    for node in (template.topology_snapshot or {}).get("nodes") or []:
        if node.get("node_type") != "corridor":
            continue
        coord = _coord_from_values(node.get("hex_q"), node.get("hex_r"))
        if coord is None or coord in excluded_corridor_set:
            continue
        reserved_coords[coord] = "corridor"
    for spec in template.human_specs or []:
        coord = _coord_from_values(spec.get("hex_q"), spec.get("hex_r"))
        if coord is not None:
            reserved_coords[coord] = "human"

    normalized_positions: list[dict[str, int]] = []
    occupied_by_agent: dict[tuple[int, int], int] = {}
    for idx in selected_indices:
        spec = agent_specs[idx]
        raw_pos = override_by_index.get(idx)
        if raw_pos is None and require_explicit_agent_positions:
            issues.append(_layout_issue(
                "missing_position",
                "Agent 缺少确认坐标，请先放置到空位",
                agent_index=idx,
            ))
            continue
        raw_pos = raw_pos or spec
        has_q = "hex_q" in raw_pos and raw_pos.get("hex_q") is not None
        has_r = "hex_r" in raw_pos and raw_pos.get("hex_r") is not None
        if not has_q or not has_r:
            issues.append(_layout_issue(
                "missing_position",
                "Agent 缺少坐标，请先放置到空位",
                agent_index=idx,
            ))
            continue
        coord = _coord_from_values(raw_pos.get("hex_q"), raw_pos.get("hex_r"))
        if coord is None:
            issues.append(_layout_issue(
                "invalid_position",
                "Agent 坐标必须是整数",
                agent_index=idx,
            ))
            continue

        conflict = reserved_coords.get(coord)
        if conflict:
            code = "blackboard_conflict" if conflict == "blackboard" else "reserved_conflict"
            message = "Agent 不能放置在黑板位置" if conflict == "blackboard" else "Agent 不能放置在保留节点位置"
            issues.append(_layout_issue(
                code,
                message,
                agent_index=idx,
                hex_q=coord[0],
                hex_r=coord[1],
                conflict_with=conflict,
            ))

        previous = occupied_by_agent.get(coord)
        if previous is not None:
            issues.append(_layout_issue(
                "duplicate_position",
                "多个选中 Agent 使用了同一坐标",
                agent_index=idx,
                hex_q=coord[0],
                hex_r=coord[1],
                conflict_with=f"agent:{previous}",
            ))
        else:
            occupied_by_agent[coord] = idx

        normalized_positions.append({"agent_index": idx, "hex_q": coord[0], "hex_r": coord[1]})

    return {
        "can_deploy": not issues and bool(selected_indices),
        "selected_agent_indices": selected_indices,
        "excluded_corridor_coords": excluded_corridors,
        "agent_positions": normalized_positions,
        "issues": issues,
    }


def _build_agent_specs_with_layout(
    all_agent_specs: list[dict],
    selected_indices: list[int],
    agent_positions: list[dict[str, int]],
) -> tuple[list[dict], dict[tuple[int, int], tuple[int, int]]]:
    position_by_index = {
        p["agent_index"]: (p["hex_q"], p["hex_r"])
        for p in agent_positions
    }
    coord_rewrites: dict[tuple[int, int], tuple[int, int]] = {}
    selected_specs: list[dict] = []
    for idx in selected_indices:
        spec = deepcopy(all_agent_specs[idx])
        new_coord = position_by_index[idx]
        old_coord = _coord_from_values(spec.get("hex_q"), spec.get("hex_r"))
        if old_coord is not None and old_coord != new_coord:
            coord_rewrites[old_coord] = new_coord
        spec["hex_q"] = new_coord[0]
        spec["hex_r"] = new_coord[1]
        selected_specs.append(spec)
    return selected_specs, coord_rewrites


async def _wait_deploy_finished(deploy_id: str, timeout_s: float = 1200.0) -> tuple[bool, str | None]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        async with async_session_factory() as db:
            r = await db.execute(select(DeployRecord).where(DeployRecord.id == deploy_id))
            rec = r.scalar_one_or_none()
            if rec and rec.status in (DeployStatus.success, DeployStatus.failed):
                return rec.status == DeployStatus.success, rec.message
        await asyncio.sleep(3)
    return False, "部署等待超时"


async def _run_deploy_pipeline(workspace_deploy_id: str) -> None:
    try:
        await _run_deploy_pipeline_inner(workspace_deploy_id)
    except Exception as e:
        logger.exception("workspace template deploy failed: %s", workspace_deploy_id)
        async with async_session_factory() as db:
            r = await db.execute(
                select(WorkspaceDeploy).where(WorkspaceDeploy.id == workspace_deploy_id)
            )
            wd = r.scalar_one_or_none()
            if wd:
                wd.status = "failed"
                detail = dict(wd.progress_detail or {})
                detail["error"] = str(e)
                wd.progress_detail = detail
                await db.commit()
        _publish(workspace_deploy_id, "complete", {"status": "failed", "error": str(e)})


def _filter_topology_by_exclusions(
    topo_snap: dict,
    all_agent_specs: list[dict],
    selected_agent_indices: list[int],
    excluded_corridor_coords: list[list[int]] | None,
    coord_rewrites: dict[tuple[int, int], tuple[int, int]] | None = None,
) -> dict:
    """Filter topology nodes and edges based on user selections.

    Removes edges touching excluded agents and excluded corridors,
    then removes excluded corridor nodes from the node list.
    """
    excluded_agent_set = {
        (s.get("hex_q"), s.get("hex_r"))
        for i, s in enumerate(all_agent_specs)
        if i not in set(selected_agent_indices)
    }
    excluded_corridor_set = (
        {(c[0], c[1]) for c in excluded_corridor_coords if len(c) >= 2}
        if excluded_corridor_coords
        else set()
    )
    all_excluded = excluded_agent_set | excluded_corridor_set
    rewrites = coord_rewrites or {}

    edges = [
        {
            **e,
            "a_q": rewrites.get((e.get("a_q"), e.get("a_r")), (e.get("a_q"), e.get("a_r")))[0],
            "a_r": rewrites.get((e.get("a_q"), e.get("a_r")), (e.get("a_q"), e.get("a_r")))[1],
            "b_q": rewrites.get((e.get("b_q"), e.get("b_r")), (e.get("b_q"), e.get("b_r")))[0],
            "b_r": rewrites.get((e.get("b_q"), e.get("b_r")), (e.get("b_q"), e.get("b_r")))[1],
        }
        for e in (topo_snap.get("edges") or [])
        if (e.get("a_q"), e.get("a_r")) not in all_excluded
        and (e.get("b_q"), e.get("b_r")) not in all_excluded
    ]

    nodes = [
        {
            **n,
            "hex_q": rewrites.get((n.get("hex_q"), n.get("hex_r")), (n.get("hex_q"), n.get("hex_r")))[0],
            "hex_r": rewrites.get((n.get("hex_q"), n.get("hex_r")), (n.get("hex_q"), n.get("hex_r")))[1],
        }
        for n in (topo_snap.get("nodes") or [])
        if n.get("node_type") != "corridor"
        or (n.get("hex_q"), n.get("hex_r")) not in excluded_corridor_set
    ]

    return {**topo_snap, "nodes": nodes, "edges": edges}


async def _run_deploy_pipeline_inner(workspace_deploy_id: str) -> None:
    async with async_session_factory() as db:
        r = await db.execute(
            select(WorkspaceDeploy).where(WorkspaceDeploy.id == workspace_deploy_id)
        )
        wd = r.scalar_one_or_none()
        if not wd:
            return
        tpl = (
            await db.execute(
                select(WorkspaceTemplate).where(
                    WorkspaceTemplate.id == wd.template_id,
                    not_deleted(WorkspaceTemplate),
                )
            )
        ).scalar_one_or_none()
        if not tpl:
            wd.status = "failed"
            await db.commit()
            return
        user = (await db.execute(select(User).where(User.id == wd.created_by))).scalar_one_or_none()
        if not user:
            wd.status = "failed"
            await db.commit()
            return
        deploy_user_id = user.id
        workspace_id = wd.workspace_id
        cfg = wd.config_snapshot or {}
        cluster_id = cfg.get("cluster_id")
        org_id = wd.org_id
        all_agent_specs: list[dict] = list(tpl.agent_specs or [])
        selected_indices = _selected_agent_indices(
            all_agent_specs,
            cfg.get("selected_agent_indices"),
        )
        agent_positions = cfg.get("agent_positions") or []
        agent_specs, coord_rewrites = _build_agent_specs_with_layout(
            all_agent_specs,
            selected_indices,
            agent_positions,
        )
        human_specs: list[dict] = list(tpl.human_specs or [])
        topo_snap = dict(tpl.topology_snapshot or {})
        bb_snap = tpl.blackboard_snapshot or {}
        excluded_corridor_coords: list[list[int]] | None = cfg.get("excluded_corridor_coords")

        has_agent_exclusions = len(agent_specs) < len(all_agent_specs)
        has_corridor_exclusions = bool(excluded_corridor_coords)
        if has_agent_exclusions or has_corridor_exclusions or coord_rewrites:
            topo_snap = _filter_topology_by_exclusions(
                topo_snap,
                all_agent_specs,
                selected_indices,
                excluded_corridor_coords,
                coord_rewrites,
            )

        wd.status = "deploying"
        await db.commit()

    if not workspace_id:
        error_msg = "workspace deleted during deploy"
        failed_count = len(agent_specs)
        async with async_session_factory() as db:
            r = await db.execute(select(WorkspaceDeploy).where(WorkspaceDeploy.id == workspace_deploy_id))
            wd = r.scalar_one_or_none()
            if wd:
                wd.status = "failed"
                detail = dict(wd.progress_detail or {})
                detail["error"] = error_msg
                detail["current_phase"] = "done"
                detail["phases_completed"] = list(detail.get("phases_completed") or [])
                wd.failed_agents = failed_count
                wd.progress_detail = detail
                await db.commit()
        _publish(
            workspace_deploy_id,
            "complete",
            {
                "status": "failed",
                "error": error_msg,
                "success_count": 0,
                "failed_count": failed_count,
            },
        )
        return

    _publish(workspace_deploy_id, "phase", {"phase": "blackboard", "message": "应用黑板内容"})

    async with async_session_factory() as db:
        if "content" in bb_snap:
            bb_row = (
                await db.execute(
                    select(Blackboard).where(
                        Blackboard.workspace_id == workspace_id,
                        Blackboard.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if bb_row:
                bb_row.content = bb_snap["content"]
                await db.commit()

    _publish(workspace_deploy_id, "phase", {"phase": "deploy_agents", "message": "正在部署 Agent"})

    instance_by_index: dict[int, str] = {}
    deploy_ids: dict[int, str] = {}
    errors: dict[int, str] = {}

    sem = asyncio.Semaphore(3)

    async def deploy_one(idx: int, spec: dict) -> None:
        nonlocal instance_by_index, deploy_ids, errors
        name_base = spec.get("display_name") or f"agent-{idx}"
        unique_name = f"{name_base}-{uuid.uuid4().hex[:6]}"
        resources = spec.get("resources") or {}
        runtime = spec.get("runtime") or "openclaw"
        async with sem:
            _publish(
                workspace_deploy_id, "agent_progress",
                {"display_name": name_base, "status": "deploying", "index": idx},
            )
            last_err: str | None = None
            for attempt in range(2):
                attempt_name = unique_name if attempt == 0 else f"{unique_name}-r{attempt}"
                rec_deploy_id: str | None = None
                inst_uuid: str | None = None
                async with async_session_factory() as db_inner:
                    urow = await db_inner.execute(select(User).where(User.id == deploy_user_id))
                    deploy_user = urow.scalar_one_or_none()
                    if not deploy_user:
                        last_err = "用户不存在"
                        break
                    cluster = await _get_org_cluster(db_inner, cluster_id, org_id)
                    if not cluster:
                        last_err = "集群不存在"
                        break
                    spec_cp = spec.get("compute_provider") or "k8s"
                    if cluster.compute_provider != spec_cp:
                        last_err = (
                            f"集群类型 {cluster.compute_provider} 与模板 Agent 所需 {spec_cp} 不一致"
                        )
                        break
                    llm_items = await _build_llm_configs(
                        db_inner, org_id, spec.get("llm_providers") or [],
                    )
                    image_version = await _resolve_image_version(db_inner, runtime)
                    cpu_limit = resources.get("cpu_limit", "2000m")
                    mem_limit = resources.get("mem_limit", "2Gi")
                    req = DeployRequest(
                        cluster_id=cluster_id,
                        name=attempt_name,
                        image_version=image_version,
                        cpu_request=resources.get("cpu_request", "500m"),
                        cpu_limit=cpu_limit,
                        mem_request=resources.get("mem_request", "2Gi"),
                        mem_limit=mem_limit,
                        storage_size=resources.get("storage_size", "80Gi"),
                        quota_cpu=resources.get("quota_cpu") or cpu_limit,
                        quota_mem=resources.get("quota_mem") or mem_limit,
                        llm_configs=llm_items or None,
                        runtime=runtime,
                    )
                    try:
                        dep_id, ctx = await deploy_service.deploy_instance(
                            req, deploy_user, db_inner, org_id=org_id,
                        )
                        rec_deploy_id = dep_id
                        inst_uuid = ctx.instance_id
                        task = asyncio.create_task(
                            deploy_service.execute_deploy_pipeline(ctx),
                            name=f"tpl-deploy-{dep_id}",
                        )
                        deploy_service.register_deploy_task(dep_id, task)
                    except Exception as e:
                        last_err = str(e)
                        logger.warning("deploy_instance failed: %s", e)
                        continue
                if not rec_deploy_id or not inst_uuid:
                    continue
                ok, msg = await _wait_deploy_finished(rec_deploy_id)
                if ok:
                    instance_by_index[idx] = inst_uuid
                    deploy_ids[idx] = rec_deploy_id
                    _publish(
                        workspace_deploy_id, "agent_progress",
                        {"display_name": name_base, "status": "success", "index": idx},
                    )
                    return
                last_err = msg or "部署失败"
            errors[idx] = last_err or "部署失败"
            _publish(
                workspace_deploy_id, "agent_progress",
                {
                    "display_name": name_base,
                    "status": "failed",
                    "index": idx,
                    "error": errors[idx],
                },
            )

    await asyncio.gather(*[deploy_one(i, s) for i, s in enumerate(agent_specs)])

    agents_progress = []
    for i, spec in enumerate(agent_specs):
        name_base = spec.get("display_name") or f"agent-{i}"
        if i in instance_by_index:
            agents_progress.append({
                "display_name": name_base,
                "instance_id": instance_by_index[i],
                "deploy_id": deploy_ids.get(i),
                "status": "success",
                "step": "deploy",
                "error": None,
                "retry_count": 0,
            })
        else:
            agents_progress.append({
                "display_name": name_base,
                "instance_id": None,
                "deploy_id": None,
                "status": "failed",
                "step": "deploy",
                "error": errors.get(i),
                "retry_count": 1,
            })

    async with async_session_factory() as db:
        r = await db.execute(
            select(WorkspaceDeploy).where(WorkspaceDeploy.id == workspace_deploy_id)
        )
        wd = r.scalar_one_or_none()
        if wd:
            wd.progress_detail = {
                "agents": agents_progress,
                "current_phase": "install_genes",
                "phases_completed": ["create_workspace", "deploy_agents"],
            }
            wd.completed_agents = sum(1 for a in agents_progress if a["status"] == "success")
            wd.failed_agents = sum(1 for a in agents_progress if a["status"] == "failed")
            await db.commit()

    _publish(workspace_deploy_id, "phase", {"phase": "install_genes", "message": "正在安装基因"})

    for i, spec in enumerate(agent_specs):
        if i not in instance_by_index:
            continue
        inst_id = instance_by_index[i]
        name_base = spec.get("display_name") or f"agent-{i}"
        _publish(
            workspace_deploy_id, "agent_progress",
            {"display_name": name_base, "status": "gene_install", "index": i},
        )
        for slug in spec.get("gene_slugs") or []:
            try:
                await install_gene_prerestart(inst_id, slug)
            except Exception as e:
                logger.warning("gene install skipped %s on %s: %s", slug, inst_id, e)
        async with async_session_factory() as db_mcp:
            for ms in spec.get("mcp_servers") or []:
                nm = ms.get("name")
                if not nm:
                    continue
                exists = await db_mcp.execute(
                    select(InstanceMcpServer.id).where(
                        InstanceMcpServer.instance_id == inst_id,
                        InstanceMcpServer.name == nm,
                        not_deleted(InstanceMcpServer),
                    ).limit(1)
                )
                if exists.scalar_one_or_none():
                    continue
                raw_args = ms.get("args")
                args_val = raw_args if isinstance(raw_args, dict) else {}
                db_mcp.add(
                    InstanceMcpServer(
                        id=str(uuid.uuid4()),
                        instance_id=inst_id,
                        name=nm,
                        transport=ms.get("transport") or "stdio",
                        command=ms.get("command"),
                        url=ms.get("url"),
                        args=args_val,
                        env={},
                        is_active=True,
                        source=ms.get("source") or "manual",
                    )
                )
            await db_mcp.commit()

    _publish(workspace_deploy_id, "phase", {"phase": "setup_topology", "message": "配置拓扑"})

    user_id = deploy_user_id
    for i, spec in enumerate(agent_specs):
        if i not in instance_by_index:
            continue
        inst_id = instance_by_index[i]
        name_base = spec.get("display_name") or f"agent-{i}"
        _publish(
            workspace_deploy_id, "agent_progress",
            {"display_name": name_base, "status": "add_workspace", "index": i},
        )
        async with async_session_factory() as db_add:
            try:
                await workspace_service.add_agent(
                    db_add,
                    workspace_id,
                    AddAgentRequest(
                        instance_id=inst_id,
                        display_name=spec.get("display_name"),
                        label=spec.get("label"),
                        hex_q=spec["hex_q"],
                        hex_r=spec["hex_r"],
                        install_gene_slugs=[],
                    ),
                    user_id,
                )
                _publish(
                    workspace_deploy_id, "agent_progress",
                    {"display_name": name_base, "status": "success", "index": i},
                )
            except Exception as e:
                logger.error("add_agent failed: %s", e)
                _publish(
                    workspace_deploy_id, "agent_progress",
                    {"display_name": name_base, "status": "add_workspace_failed", "error": str(e), "index": i},
                )

    async with async_session_factory() as db_topo:
        await workspace_service.apply_internal_deploy_topology(
            db_topo, workspace_id, user_id, topo_snap, human_specs,
        )

    success_n = len(instance_by_index)
    fail_n = len(agent_specs) - success_n
    final_status = "success" if fail_n == 0 else "partial_success"

    async with async_session_factory() as db:
        r = await db.execute(
            select(WorkspaceDeploy).where(WorkspaceDeploy.id == workspace_deploy_id)
        )
        wd = r.scalar_one_or_none()
        if wd:
            wd.status = final_status
            detail = dict(wd.progress_detail or {})
            detail["current_phase"] = "done"
            detail["phases_completed"] = [
                "create_workspace", "deploy_agents", "install_genes", "setup_topology",
            ]
            wd.progress_detail = detail
            await db.commit()

    _publish(
        workspace_deploy_id, "complete",
        {"status": final_status, "success_count": success_n, "failed_count": fail_n},
    )


async def start_workspace_template_deploy(
    db: AsyncSession,
    *,
    template: WorkspaceTemplate,
    workspace_name: str,
    cluster_id: str,
    user: User,
    org_id: str,
    selected_agent_indices: list[int] | None = None,
    excluded_corridor_coords: list[list[int]] | None = None,
    agent_positions: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    all_agent_specs = list(template.agent_specs or [])
    if not all_agent_specs:
        raise ValueError("该模板不支持一键部署（缺少 agent_specs）")

    selected_indices = _selected_agent_indices(all_agent_specs, selected_agent_indices)
    if not selected_indices:
        raise ValueError("至少选择一个 Agent 进行部署")
    selected_specs_for_validation = [all_agent_specs[i] for i in selected_indices]
    providers = {s.get("compute_provider") or "k8s" for s in selected_specs_for_validation}
    if len(providers) > 1:
        raise ValueError("模板包含多种计算平台（K8s/Docker 混用），无法一键部署")

    cluster = await _get_org_cluster(db, cluster_id, org_id)
    if not cluster:
        raise ValueError("集群不存在")
    need = next(iter(providers))
    if cluster.compute_provider != need:
        raise ValueError(f"请选择 {need} 类型的集群以匹配模板")

    layout = prepare_template_deploy_layout(
        template,
        selected_agent_indices=selected_agent_indices,
        excluded_corridor_coords=excluded_corridor_coords,
        agent_positions=agent_positions,
        require_explicit_agent_positions=True,
    )
    if not layout["can_deploy"]:
        raise ValueError("模板部署布局未通过校验")

    agent_specs, _coord_rewrites = _build_agent_specs_with_layout(
        all_agent_specs,
        selected_indices,
        layout["agent_positions"],
    )

    ws = await workspace_service.create_workspace(
        db,
        org_id,
        user.id,
        WorkspaceCreate(name=workspace_name, description=template.description or "", cluster_id=cluster_id),
    )

    ws_row = await db.get(Workspace, ws.id)
    ws_row.source_template_id = template.id

    wd = WorkspaceDeploy(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        template_id=template.id,
        status="pending",
        total_agents=len(agent_specs),
        completed_agents=0,
        failed_agents=0,
        progress_detail={
            "agents": [
                {
                    "display_name": s.get("display_name") or f"agent-{i}",
                    "instance_id": None,
                    "status": "pending",
                    "step": None,
                    "error": None,
                    "retry_count": 0,
                }
                for i, s in enumerate(agent_specs)
            ],
            "current_phase": "pending",
            "phases_completed": [],
        },
        config_snapshot={
            "cluster_id": cluster_id,
            "workspace_name": workspace_name,
            "selected_agent_indices": selected_indices,
            "excluded_corridor_coords": layout["excluded_corridor_coords"],
            "agent_positions": layout["agent_positions"],
        },
        created_by=user.id,
        org_id=org_id,
    )
    db.add(wd)
    await db.commit()

    asyncio.create_task(
        _run_deploy_pipeline(wd.id),
        name=f"ws-tpl-deploy-{wd.id}",
    )

    return {"workspace_deploy_id": wd.id, "workspace_id": ws.id}
