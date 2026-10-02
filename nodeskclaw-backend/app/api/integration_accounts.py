from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.common import ApiResponse
from app.services.integration_account_service import IntegrationAccountService

router = APIRouter(prefix="/integrations", tags=["Integrations"])


class ConnectBody(BaseModel):
    toolkit_slug: str
    alias: str | None = None


def _ok(data):
    return ApiResponse(data=data)


@router.get("/accounts")
async def list_integration_accounts(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    rows = await IntegrationAccountService(db).list_accounts(org_id=org.id, user_id=user.id)
    return _ok(rows)


@router.get("/accounts/{account_id}")
async def get_integration_account(
    account_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    row = await IntegrationAccountService(db).get_account(org_id=org.id, user_id=user.id, account_id=account_id)
    return _ok(row)


@router.post("/composio/connect")
async def connect_composio_account(
    body: ConnectBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    result = await IntegrationAccountService(db).connect(
        org_id=org.id,
        user_id=user.id,
        toolkit_slug=body.toolkit_slug,
        alias=body.alias,
    )
    return _ok(result)


@router.post("/accounts/{account_id}/complete")
async def complete_composio_account(
    account_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    row = await IntegrationAccountService(db).complete(org_id=org.id, user_id=user.id, account_id=account_id)
    return _ok(row)


@router.post("/accounts/{account_id}/reauthorize")
async def reauthorize_composio_account(
    account_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    result = await IntegrationAccountService(db).reauthorize(org_id=org.id, user_id=user.id, account_id=account_id)
    return _ok(result)


@router.post("/accounts/{account_id}/disconnect")
async def disconnect_composio_account(
    account_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    row = await IntegrationAccountService(db).disconnect(org_id=org.id, user_id=user.id, account_id=account_id)
    return _ok(row)


@router.delete("/accounts/{account_id}")
async def delete_composio_account(
    account_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await IntegrationAccountService(db).delete_account(org_id=org.id, user_id=user.id, account_id=account_id)
    return _ok({"deleted": True})
