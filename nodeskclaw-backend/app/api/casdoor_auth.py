"""Desktop Casdoor login. The browser callback never returns a LoginResponse."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import hooks
from app.core.deps import get_db
from app.core.exceptions import BadRequestError
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.auth import LoginResponse
from app.schemas.common import ApiResponse
from app.services.identity import binding_service
from app.services.identity.casdoor_client import CasdoorClient

router = APIRouter()


class ExchangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=256)


def _redirect(location: str) -> RedirectResponse:
    response = RedirectResponse(url=location, status_code=302)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def _client() -> CasdoorClient:
    return CasdoorClient()


@router.get("/casdoor/login")
async def casdoor_login(
    return_to: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    client = _client()
    try:
        location = await binding_service.start_login(db, return_to, client)
    except binding_service.InvalidReturnTo:
        raise BadRequestError("回调地址无效", "errors.auth.casdoor_return_to_invalid") from None
    except binding_service.NotConfigured:
        raise BadRequestError("企业单点登录未配置", "errors.auth.casdoor_not_configured") from None
    except binding_service.LoginExpired:
        raise BadRequestError("登录已失效，请重新发起登录", "errors.auth.casdoor_login_expired") from None
    return _redirect(location)


@router.get("/casdoor/callback")
async def casdoor_callback(
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    result = await binding_service.finish_callback(
        db,
        state=state,
        code=code,
        error=error,
        client=_client(),
    )
    if result.location is None:
        raise BadRequestError("登录已失效，请重新发起登录", "errors.auth.casdoor_login_expired")
    return _redirect(result.location)


@router.post("/casdoor/exchange", response_model=ApiResponse[LoginResponse])
async def casdoor_exchange(
    body: ExchangeRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await binding_service.exchange_code(db, body.code, _client())
    except binding_service.NotConfigured:
        raise BadRequestError("企业单点登录未配置", "errors.auth.casdoor_not_configured") from None
    except binding_service.LoginExpired:
        raise BadRequestError("登录已失效，请重新发起登录", "errors.auth.casdoor_login_expired") from None
    await hooks.emit(
        "operation_audit",
        action="auth.login",
        target_type="user",
        target_id=result.user.id,
        actor_id=result.user.id,
        org_id=result.user.current_org_id,
        details={"method": "casdoor"},
    )
    return ApiResponse(data=result)


@router.delete("/casdoor/binding", response_model=ApiResponse)
async def casdoor_unbind(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await binding_service.unbind(db, current_user)
    except binding_service.PasswordRequired:
        raise BadRequestError("请先设置密码后再解除绑定", "errors.auth.casdoor_password_required") from None
    return ApiResponse()
