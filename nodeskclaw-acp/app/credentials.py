from __future__ import annotations

import asyncio
from urllib.parse import urlparse

import keyring

from app.config import Settings
from app.constants import KEYRING_SERVICE
from app.errors import auth_refresh_failed, auth_required, desktop_credential_invalid

ACCOUNT_ACCESS = "access_token"
ACCOUNT_REFRESH = "refresh_token"


class CredentialStore:
    def __init__(self, settings: Settings, http_refresh):
        self.settings = settings
        self._http_refresh = http_refresh
        self._lock = asyncio.Lock()
        self._memory_access = ""
        self._memory_refresh = ""

    def managed(self) -> bool:
        return (self.settings.NODESKCLAW_CREDENTIAL_MODE or "").strip().lower() == "managed"

    def _account(self) -> str:
        host = urlparse(self.settings.NODESKCLAW_BASE_URL).netloc or "nodeskclaw"
        return host

    def env_access_token(self) -> str:
        return (self.settings.NODESKCLAW_ACCESS_TOKEN or "").strip()

    def env_refresh_token(self) -> str:
        return (self.settings.NODESKCLAW_REFRESH_TOKEN or "").strip()

    def keyring_get(self, kind: str) -> str:
        if self.managed():
            return ""
        try:
            return (keyring.get_password(KEYRING_SERVICE, f"{self._account()}:{kind}") or "").strip()
        except Exception:
            return ""

    def keyring_set(self, kind: str, value: str) -> None:
        if self.managed():
            raise desktop_credential_invalid()
        keyring.set_password(KEYRING_SERVICE, f"{self._account()}:{kind}", value)

    def keyring_clear(self) -> None:
        if self.managed():
            return
        for kind in (ACCOUNT_ACCESS, ACCOUNT_REFRESH):
            try:
                keyring.delete_password(KEYRING_SERVICE, f"{self._account()}:{kind}")
            except Exception:
                pass

    async def resolve_access_token(self) -> str:
        if self.managed():
            if self._memory_access:
                return self._memory_access
            access = self.env_access_token()
            refresh = self.env_refresh_token()
            if not access or not refresh:
                raise desktop_credential_invalid()
            self._memory_access = access
            self._memory_refresh = refresh
            return access
        env = self.env_access_token()
        if env:
            return env
        stored = self.keyring_get(ACCOUNT_ACCESS)
        if stored:
            return stored
        refresh = self.keyring_get(ACCOUNT_REFRESH)
        if refresh:
            return await self.refresh_once()
        raise auth_required()

    def current_refresh(self) -> str:
        if self.managed():
            return self._memory_refresh or self.env_refresh_token()
        return self.keyring_get(ACCOUNT_REFRESH)

    async def refresh_once(self) -> str:
        async with self._lock:
            refresh = self.current_refresh()
            if not refresh:
                raise auth_refresh_failed()
            tokens = await self._http_refresh(refresh)
            access = str(tokens.get("access_token") or "")
            new_refresh = str(tokens.get("refresh_token") or refresh)
            if not access:
                raise auth_refresh_failed()
            if self.managed():
                self._memory_access = access
                self._memory_refresh = new_refresh
                return access
            try:
                self.keyring_set(ACCOUNT_ACCESS, access)
                self.keyring_set(ACCOUNT_REFRESH, new_refresh)
            except Exception as exc:
                raise auth_refresh_failed() from exc
            return access

    def store_login_tokens(self, access: str, refresh: str) -> None:
        if self.managed():
            raise desktop_credential_invalid()
        if not access:
            raise auth_required()
        self.keyring_set(ACCOUNT_ACCESS, access)
        if refresh:
            self.keyring_set(ACCOUNT_REFRESH, refresh)
