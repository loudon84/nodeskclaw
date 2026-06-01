"""Spec presets read API: return instance spec presets with derived resource values."""

import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.spec_preset import (
    DEFAULT_SPEC_PRESETS,
    SpecPresetInput,
    SpecPresetOutput,
    derive_preset,
)
from app.services import config_service

logger = logging.getLogger(__name__)

router = APIRouter()

CONFIG_KEY = "instance_spec_presets"


@router.get("", response_model=ApiResponse[list[SpecPresetOutput]])
async def get_spec_presets(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    raw = await config_service.get_config(CONFIG_KEY, db)
    if raw is None:
        presets = [SpecPresetInput(**p) for p in DEFAULT_SPEC_PRESETS]
    else:
        try:
            items = json.loads(raw)
            presets = [SpecPresetInput.model_validate(item) for item in items]
        except Exception:
            logger.warning("Failed to parse spec presets from DB, using defaults")
            presets = [SpecPresetInput(**p) for p in DEFAULT_SPEC_PRESETS]

    return ApiResponse(data=[derive_preset(p) for p in presets])
