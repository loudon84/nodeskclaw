"""Member model credential endpoints."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_admin, require_org_member
from app.schemas.common import ApiResponse
from app.services import member_token_service

router = APIRouter()


class CreateMemberTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: Literal["new-api", "deepseek", "custom"]
    provider_group: str | None = None
    base_url: str | None = None
    token: str | None = None
    models: dict | None = None
    is_default: bool = False


class UpdateMemberTokenRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_group: str | None = None
    base_url: str | None = None
    token: str | None = None
    models: dict | None = None
    is_active: bool | None = None
    is_default: bool | None = None


@router.get("/{org_id}/new-api/groups", response_model=ApiResponse)
async def list_new_api_groups(
    org_id: str,
    _org_ctx: tuple = Depends(require_org_admin),
):
    items = await member_token_service.list_new_api_groups()
    return ApiResponse(data={"items": items})


@router.get("/{org_id}/member-tokens/pending-close", response_model=ApiResponse)
async def list_pending_close(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    _org_ctx: tuple = Depends(require_org_admin),
):
    items = await member_token_service.list_pending_close_tokens(db, org_id=org_id)
    return ApiResponse(data={"items": items})


@router.get("/{org_id}/members/{membership_id}/tokens", response_model=ApiResponse)
async def list_tokens(
    org_id: str,
    membership_id: str,
    db: AsyncSession = Depends(get_db),
    org_ctx: tuple = Depends(require_org_member),
):
    items = await member_token_service.list_member_tokens(
        db,
        org_id=org_id,
        membership_id=membership_id,
        caller=org_ctx[0],
    )
    return ApiResponse(data={"items": items})


@router.post("/{org_id}/members/{membership_id}/tokens", response_model=ApiResponse)
async def create_token(
    org_id: str,
    membership_id: str,
    body: CreateMemberTokenRequest,
    db: AsyncSession = Depends(get_db),
    org_ctx: tuple = Depends(require_org_admin),
):
    data = await member_token_service.create_member_token(
        db,
        org_id=org_id,
        membership_id=membership_id,
        actor=org_ctx[0],
        provider=body.provider,
        provider_group=body.provider_group,
        base_url=body.base_url,
        plaintext=body.token,
        models=body.models,
        is_default=body.is_default,
        fields_set=set(body.model_fields_set),
    )
    return ApiResponse(data=data)


@router.get("/{org_id}/members/{membership_id}/tokens/{token_id}", response_model=ApiResponse)
async def get_token(
    org_id: str,
    membership_id: str,
    token_id: str,
    db: AsyncSession = Depends(get_db),
    org_ctx: tuple = Depends(require_org_member),
):
    data = await member_token_service.get_member_token(
        db,
        org_id=org_id,
        membership_id=membership_id,
        token_id=token_id,
        caller=org_ctx[0],
    )
    return ApiResponse(data=data)


@router.patch("/{org_id}/members/{membership_id}/tokens/{token_id}", response_model=ApiResponse)
async def update_token(
    org_id: str,
    membership_id: str,
    token_id: str,
    body: UpdateMemberTokenRequest,
    db: AsyncSession = Depends(get_db),
    org_ctx: tuple = Depends(require_org_admin),
):
    data = await member_token_service.update_member_token(
        db,
        org_id=org_id,
        membership_id=membership_id,
        token_id=token_id,
        actor=org_ctx[0],
        fields=body.model_dump(exclude_unset=True),
    )
    return ApiResponse(data=data)


@router.delete("/{org_id}/members/{membership_id}/tokens/{token_id}", response_model=ApiResponse)
async def delete_token(
    org_id: str,
    membership_id: str,
    token_id: str,
    db: AsyncSession = Depends(get_db),
    org_ctx: tuple = Depends(require_org_admin),
):
    await member_token_service.delete_member_token(
        db,
        org_id=org_id,
        membership_id=membership_id,
        token_id=token_id,
        actor=org_ctx[0],
    )
    return ApiResponse(message="deleted")


@router.post(
    "/{org_id}/members/{membership_id}/tokens/{token_id}/reveal",
    response_model=ApiResponse,
)
async def reveal_token(
    org_id: str,
    membership_id: str,
    token_id: str,
    db: AsyncSession = Depends(get_db),
    org_ctx: tuple = Depends(require_org_member),
):
    data = await member_token_service.reveal_member_token(
        db,
        org_id=org_id,
        membership_id=membership_id,
        token_id=token_id,
        caller=org_ctx[0],
    )
    return ApiResponse(data=data)


@router.post(
    "/{org_id}/members/{membership_id}/tokens/{token_id}/retry-revoke",
    response_model=ApiResponse,
)
async def retry_revoke_token(
    org_id: str,
    membership_id: str,
    token_id: str,
    db: AsyncSession = Depends(get_db),
    org_ctx: tuple = Depends(require_org_admin),
):
    data = await member_token_service.retry_revoke_member_token(
        db,
        org_id=org_id,
        membership_id=membership_id,
        token_id=token_id,
        actor=org_ctx[0],
    )
    return ApiResponse(data=data)


@router.post(
    "/{org_id}/members/{membership_id}/tokens/{token_id}/close-local",
    response_model=ApiResponse,
)
async def close_local_token(
    org_id: str,
    membership_id: str,
    token_id: str,
    db: AsyncSession = Depends(get_db),
    org_ctx: tuple = Depends(require_org_admin),
):
    data = await member_token_service.close_local_member_token(
        db,
        org_id=org_id,
        membership_id=membership_id,
        token_id=token_id,
        actor=org_ctx[0],
    )
    return ApiResponse(data=data)
