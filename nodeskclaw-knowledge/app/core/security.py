"""JWT validation helpers."""

from fastapi import HTTPException, status
from jose import JWTError, jwt

from app.core.config import settings

_ALLOWED_TOKEN_TYPES = {"access"}


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": 40101,
                "message_key": "errors.auth.token_invalid",
                "message": "Token 无效或已过期",
            },
        )


def extract_user_id(payload: dict) -> str:
    if payload.get("type") not in _ALLOWED_TOKEN_TYPES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": 40102,
                "message_key": "errors.auth.token_type_invalid",
                "message": "Token 类型错误",
            },
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error_code": 40104,
                "message_key": "errors.auth.token_subject_missing",
                "message": "Token 无效",
            },
        )
    return str(user_id)
