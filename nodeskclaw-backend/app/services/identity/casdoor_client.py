"""Casdoor OIDC calls. Tokens from Casdoor are returned to the caller and never stored."""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class CasdoorUnavailable(Exception):
    """Discovery, token exchange, or userinfo failed. Callers map this to idp_failed."""


class CasdoorClient:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    def configured(self) -> bool:
        return bool(
            settings.CASDOOR_ISSUER.strip()
            and settings.CASDOOR_CLIENT_ID.strip()
            and settings.CASDOOR_CLIENT_SECRET.strip()
            and settings.CASDOOR_REDIRECT_URI.strip()
        )

    async def discover(self) -> dict[str, str]:
        issuer = settings.CASDOOR_ISSUER.strip().rstrip("/")
        document = await self._get_json(f"{issuer}/.well-known/openid-configuration")
        try:
            return {
                "authorization_endpoint": document["authorization_endpoint"],
                "token_endpoint": document["token_endpoint"],
                "userinfo_endpoint": document["userinfo_endpoint"],
            }
        except (KeyError, TypeError) as exc:
            logger.warning("casdoor discovery document missing endpoints")
            raise CasdoorUnavailable from exc

    async def exchange_code(self, token_endpoint: str, code: str, code_verifier: str) -> str:
        payload = await self._post_form(
            token_endpoint,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.CASDOOR_REDIRECT_URI,
                "client_id": settings.CASDOOR_CLIENT_ID,
                "client_secret": settings.CASDOOR_CLIENT_SECRET,
                "code_verifier": code_verifier,
            },
        )
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            logger.warning("casdoor token response missing access token")
            raise CasdoorUnavailable
        return token

    async def userinfo(self, userinfo_endpoint: str, access_token: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport) as client:
                response = await client.get(
                    userinfo_endpoint,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("casdoor userinfo failed")
            raise CasdoorUnavailable from exc
        if not isinstance(payload, dict):
            raise CasdoorUnavailable
        return payload

    async def _get_json(self, url: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport) as client:
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("casdoor discovery failed")
            raise CasdoorUnavailable from exc
        if not isinstance(payload, dict):
            raise CasdoorUnavailable
        return payload

    async def _post_form(self, url: str, data: dict[str, str]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport) as client:
                response = await client.post(url, data=data)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("casdoor token exchange failed")
            raise CasdoorUnavailable from exc
        if not isinstance(payload, dict):
            raise CasdoorUnavailable
        return payload


_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
