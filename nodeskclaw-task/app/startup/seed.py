"""Seed AutoTask mock data."""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.artifact import Artifact
from app.models.audit_log import AuditLog
from app.models.automation_task import AutomationTask
from app.models.autotask_setting import AutotaskSetting
from app.models.base import not_deleted
from app.models.portal_access_grant import PortalAccessGrant
from app.models.portal_account import PortalAccount
from app.models.rpa_component import RpaComponent
from app.models.rpa_run import RpaRun
from app.models.rpa_worker import RpaWorker
from app.models.run_event import RunEvent
from app.models.step_run import StepRun
from app.models.workflow_binding import WorkflowBinding
from app.models.workflow_template import WorkflowTemplate
from app.services.json_utils import dumps_json

logger = logging.getLogger(__name__)

DEFAULT_TENANT_ID = "seed-tenant-001"
DEFAULT_USER_ID = "seed-user-001"


def _seed_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data" / "seed"


def _load_json(name: str) -> list | dict:
    path = _seed_dir() / name
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


async def run_seed(session_factory: async_sessionmaker) -> None:
    async with session_factory() as db:
        existing = (
            await db.execute(
                select(PortalAccount).where(
                    PortalAccount.tenant_id == DEFAULT_TENANT_ID,
                    not_deleted(PortalAccount),
                )
            )
        ).scalar_one_or_none()
        if existing:
            logger.info("种子数据已存在，跳过导入")
            return

        portals = _load_json("srm-portals.json")
        for item in portals:
            db.add(
                PortalAccount(
                    id=item.get("id"),
                    tenant_id=item.get("tenantId", DEFAULT_TENANT_ID),
                    entity_type=item["entityType"],
                    erp_entity_code=item["erpEntityCode"],
                    erp_entity_name=item["erpEntityName"],
                    portal_name=item["portalName"],
                    portal_url=item["portalUrl"],
                    login_account=item["loginAccount"],
                    credential_ref=item.get("credentialRef"),
                    client_open_mode=item.get("clientOpenMode", "webcontents"),
                    client_session_partition=item.get("clientSessionPartition", ""),
                    rpa_profile_id=item.get("rpaProfileId"),
                    status=item.get("status", "ENABLED"),
                    owner_dept_id=item.get("ownerDeptId"),
                    created_by=item.get("createdBy", DEFAULT_USER_ID),
                )
            )

        grants = _load_json("portal-access-grants.json")
        for item in grants:
            db.add(
                PortalAccessGrant(
                    id=item.get("id"),
                    portal_account_id=item["portalAccountId"],
                    subject_type=item["subjectType"],
                    subject_id=item["subjectId"],
                    permissions=dumps_json(item.get("permissions", [])),
                    granted_by=item.get("grantedBy", DEFAULT_USER_ID),
                    granted_at=item.get("grantedAt", datetime.now(UTC).isoformat()),
                )
            )

        templates = _load_json("workflow-templates.json")
        for item in templates:
            db.add(
                WorkflowTemplate(
                    id=item.get("id"),
                    tenant_id=item.get("tenantId", DEFAULT_TENANT_ID),
                    name=item["name"],
                    code=item["code"],
                    description=item.get("description"),
                    entity_type=item["entityType"],
                    category=item.get("category", ""),
                    status=item.get("status", "ENABLED"),
                    version=item.get("version", "1.0.0"),
                    input_schema=dumps_json(item.get("inputSchema", [])),
                    business_steps=dumps_json(item.get("businessSteps", [])),
                    created_by=item.get("createdBy", DEFAULT_USER_ID),
                )
            )

        bindings = _load_json("workflow-bindings.json")
        for item in bindings:
            db.add(
                WorkflowBinding(
                    id=item.get("id"),
                    portal_account_id=item["portalAccountId"],
                    workflow_template_id=item["workflowTemplateId"],
                    workflow_template_version=item.get("workflowTemplateVersion", "1.0.0"),
                    rpa_engine_type=item.get("rpaEngineType", "PLAYWRIGHT_CDP"),
                    rpa_flow_id=item["rpaFlowId"],
                    rpa_flow_version=item.get("rpaFlowVersion", "1.0.0"),
                    rpa_flow_version_id=item.get("rpaFlowVersionId"),
                    flow_checksum_snapshot=item.get("flowChecksumSnapshot"),
                    status=item.get("status", "ENABLED"),
                    config=dumps_json(item.get("config", {})),
                    created_by=item.get("createdBy", DEFAULT_USER_ID),
                )
            )

        tasks = _load_json("tasks.json")
        for item in tasks:
            db.add(
                AutomationTask(
                    id=item.get("id"),
                    tenant_id=item.get("tenantId", DEFAULT_TENANT_ID),
                    title=item["title"],
                    task_type=item["taskType"],
                    portal_account_id=item["portalAccountId"],
                    workflow_binding_id=item["workflowBindingId"],
                    entity_type=item["entityType"],
                    erp_entity_code=item["erpEntityCode"],
                    erp_entity_name=item["erpEntityName"],
                    status=item.get("status", "DRAFT"),
                    priority=item.get("priority", "NORMAL"),
                    input=dumps_json(item.get("input", {})),
                    current_step=item.get("currentStep"),
                    progress=item.get("progress", 0),
                    created_by=item.get("createdBy", DEFAULT_USER_ID),
                    assigned_to=item.get("assignedTo"),
                )
            )

        runs_data = _load_json("task-runs.json")
        if isinstance(runs_data, dict):
            for item in runs_data.get("runs", []):
                db.add(
                    RpaRun(
                        id=item.get("id"),
                        task_id=item["taskId"],
                        rpa_flow_id=item["rpaFlowId"],
                        rpa_worker_id=item.get("rpaWorkerId"),
                        lease_id=item.get("leaseId"),
                        status=item.get("status", "QUEUED"),
                        current_step_id=item.get("currentStepId"),
                    )
                )
            for item in runs_data.get("stepRuns", []):
                db.add(
                    StepRun(
                        id=item.get("id"),
                        run_id=item["runId"],
                        step_id=item["stepId"],
                        step_name=item.get("stepName", ""),
                        status=item.get("status", "PENDING"),
                        output=dumps_json(item.get("output", {})),
                    )
                )
            for item in runs_data.get("events", []):
                db.add(
                    RunEvent(
                        id=item.get("id"),
                        run_id=item["runId"],
                        task_id=item["taskId"],
                        worker_id=item.get("workerId"),
                        type=item["type"],
                        level=item.get("level", "INFO"),
                        message=item["message"],
                        payload=dumps_json(item.get("payload", {})),
                    )
                )

        workers = _load_json("workers.json")
        for item in workers:
            db.add(
                RpaWorker(
                    worker_id=item["id"],
                    worker_type=item["workerType"],
                    device_name=item["deviceName"],
                    user_id=item.get("userId"),
                    status=item.get("status", "ONLINE"),
                    capabilities=dumps_json(item.get("capabilities", [])),
                    app_version=item.get("appVersion"),
                    agent_version=item.get("agentVersion"),
                    os=item.get("os"),
                    current_run_id=item.get("currentRunId"),
                    last_heartbeat_at=datetime.now(UTC),
                )
            )

        artifacts = _load_json("artifacts.json")
        for item in artifacts:
            db.add(
                Artifact(
                    id=item.get("id"),
                    tenant_id=item.get("tenantId", DEFAULT_TENANT_ID),
                    task_id=item["taskId"],
                    run_id=item.get("runId"),
                    type=item["type"],
                    name=item["name"],
                    storage_key=item["storageKey"],
                    size=item.get("size", 0),
                    mime_type=item.get("mimeType"),
                    created_by=item.get("createdBy"),
                )
            )

        components = _load_json("rpa-components.json")
        for item in components:
            db.add(
                RpaComponent(
                    id=item.get("id"),
                    name=item["name"],
                    type=item["type"],
                    config=dumps_json(item.get("config", {})),
                    description=item.get("description"),
                )
            )

        settings_data = _load_json("settings.json")
        if isinstance(settings_data, dict):
            for key, value in settings_data.items():
                db.add(
                    AutotaskSetting(
                        tenant_id=DEFAULT_TENANT_ID,
                        key=key,
                        value=dumps_json(value),
                    )
                )

        audit_logs = _load_json("audit-logs.json")
        for item in audit_logs:
            db.add(
                AuditLog(
                    id=item.get("id"),
                    tenant_id=item.get("tenantId", DEFAULT_TENANT_ID),
                    actor_id=item.get("actorId", DEFAULT_USER_ID),
                    action=item["action"],
                    resource_type=item["resourceType"],
                    resource_id=item["resourceId"],
                    details=dumps_json(item.get("details", {})),
                )
            )

        await db.commit()
        logger.info("种子数据导入完成")
