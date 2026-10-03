from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    NODESKCLAW_BASE_URL: str = ""
    NODESKCLAW_ACCESS_TOKEN: str = ""
    NODESKCLAW_REFRESH_TOKEN: str = ""
    NODESKCLAW_CREDENTIAL_MODE: str = "standalone"
    NODESKCLAW_ACP_MAX_SESSIONS: int = 16
    NODESKCLAW_ACP_ARTIFACT_HINTS: bool = True
