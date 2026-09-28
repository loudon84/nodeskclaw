"""Self-scoped runtime provider bootstrap. Does not call NEW-API."""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_org, get_db
from app.schemas.common import ApiResponse
from app.services import runtime_model_bootstrap_service

router = APIRouter()


class RuntimeBootstrapRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consumer: str = Field(min_length=1, max_length=64)
    runtime: str = Field(min_length=1, max_length=64)


@router.post("/runtime/model-bootstrap", response_model=ApiResponse)
async def runtime_model_bootstrap(
    body: RuntimeBootstrapRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    org_ctx: tuple = Depends(get_current_org),
):
    user, org = org_ctx
    data = await runtime_model_bootstrap_service.build_runtime_bootstrap(
        db,
        user=user,
        org_id=org.id,
        consumer=body.consumer,
        runtime=body.runtime,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return ApiResponse(data=data)
