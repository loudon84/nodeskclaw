"""Application settings."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "nodeskclaw-task"
    APP_VERSION: str = "dev"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 4520

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/nodeskclaw_task"
    DB_POOL_SIZE: int = 10
    DB_POOL_MAX_OVERFLOW: int = 20

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"

    NODESKCLAW_BACKEND_URL: str = "http://127.0.0.1:4510"
    NODESKCLAW_AUTH_ME_PATH: str = "/api/v1/auth/me"
    USER_CACHE_TTL_MINUTES: int = 10

    ARTIFACT_STORAGE: str = "local"
    ARTIFACT_LOCAL_DIR: str = "./storage/artifacts"

    CORS_ORIGINS: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    WORKER_LEASE_TTL_SECONDS: int = 120
    WORKER_HEARTBEAT_TIMEOUT_SECONDS: int = 60

    SEED_DATA_ENABLED: bool = True
    SEED_DATA_DIR: str = "app/data/seed"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = Settings()
