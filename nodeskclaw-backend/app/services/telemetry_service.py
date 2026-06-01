"""Anonymous CE installation telemetry — one-time startup ping to PostHog."""

import logging
import platform
import sys
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.feature_gate import feature_gate
from app.services import config_service

logger = logging.getLogger(__name__)

_KEY_INSTANCE_ID = "telemetry_instance_id"
_KEY_REPORTED = "telemetry_reported"


async def ensure_instance_id(db: AsyncSession) -> str:
    instance_id = await config_service.get_config(_KEY_INSTANCE_ID, db)
    if instance_id:
        return instance_id
    instance_id = str(uuid.uuid4())
    await config_service.set_config(_KEY_INSTANCE_ID, instance_id, db)
    return instance_id


async def report_installation_once(db: AsyncSession) -> None:
    if feature_gate.is_ee:
        return
    if not settings.TELEMETRY_ENABLED:
        return
    if not settings.POSTHOG_API_KEY:
        return

    reported = await config_service.get_config(_KEY_REPORTED, db)
    if reported == "true":
        logger.info("遥测已上报过，跳过")
        return

    instance_id = await ensure_instance_id(db)

    payload = {
        "api_key": settings.POSTHOG_API_KEY,
        "event": "ce_installation",
        "distinct_id": instance_id,
        "properties": {
            "$process_person_profile": False,
            "version": settings.APP_VERSION,
            "edition": feature_gate.edition,
            "python_version": sys.version.split()[0],
            "os": platform.system(),
            "arch": platform.machine(),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            url = f"{settings.POSTHOG_HOST.rstrip('/')}/i/v0/e/"
            resp = await client.post(url, json=payload)

        if resp.status_code < 300:
            await config_service.set_config(_KEY_REPORTED, "true", db)
            logger.info("已上报匿名安装信息到 PostHog (instance_id=%s)", instance_id[:8])
        else:
            logger.warning("遥测上报返回 %d，下次启动将重试", resp.status_code)
    except Exception as e:
        logger.warning("遥测上报失败（%s），下次启动将重试", e)
