"""Application settings."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "nodeskclaw-knowledge"
    APP_VERSION: str = "dev"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 4530

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/nodeskclaw_knowledge"
    DB_POOL_SIZE: int = 10
    DB_POOL_MAX_OVERFLOW: int = 20

    NODESKCLAW_BACKEND_URL: str = "http://127.0.0.1:4510"
    NODESKCLAW_KNOWLEDGE_CONTEXT_PATH: str = "/api/v1/auth/knowledge-context"
    MEMBER_CONTEXT_TTL_SECONDS: int = 0

    RAGFLOW_BASE_URL: str = "http://127.0.0.1:9380"
    RAGFLOW_API_KEY: str = ""
    RAGFLOW_TIMEOUT_SECONDS: float = 60.0
    RAGFLOW_UPLOAD_TIMEOUT_SECONDS: float = 120.0

    LLM_PROXY_URL: str = "http://127.0.0.1:4511"
    LLM_PROXY_PROVIDER: str = "openai"
    KNOWLEDGE_SERVICE_TOKEN: str = ""

    KNOWLEDGE_UPLOAD_MAX_MB: int = 200

    CHAT_HISTORY_MAX_MESSAGES: int = 20
    CHAT_HISTORY_MAX_TOKENS: int = 8000

    RETRIEVAL_DOCUMENT_BATCH_SIZE: int = 500
    RETRIEVAL_MAX_PARALLEL_SLICES: int = 8
    DEBUG_CONTENT_LOGGING: bool = False

    CORS_ORIGINS: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


settings = Settings()
