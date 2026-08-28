"""Application settings."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# @lat: [[knowledge#Feature Flags And Config]]
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
    RAGFLOW_BUILD_BATCH_SIZE: int = 50

    LLM_PROXY_URL: str = "http://127.0.0.1:4511"
    LLM_PROXY_PROVIDER: str = "openai"
    KNOWLEDGE_SERVICE_TOKEN: str = ""

    KNOWLEDGE_UPLOAD_MAX_MB: int = 200

    CHAT_HISTORY_MAX_MESSAGES: int = 20
    CHAT_HISTORY_MAX_TOKENS: int = 8000

    RETRIEVAL_DOCUMENT_BATCH_SIZE: int = 500
    RETRIEVAL_MAX_PARALLEL_SLICES: int = 8
    DEBUG_CONTENT_LOGGING: bool = False
    RAGFLOW_METADATA_PUSHDOWN_ENABLED: bool = False
    SOURCE_FRESHNESS_MAX_AGE_SECONDS: int = 86400

    KNOWLEDGE_CONNECTOR_FS_ROOTS: str = ""
    KNOWLEDGE_CONNECTOR_MASTER_KEY: str = ""
    KNOWLEDGE_HTTP_PRIVATE_NETWORK_ALLOWLIST: str = ""

    KNOWLEDGE_API_V2_ENABLED: bool = False
    KNOWLEDGE_V2_RUNTIME_BINDING_ENABLED: bool = True
    KNOWLEDGE_V2_BUILD_ENABLED: bool = False
    KNOWLEDGE_V2_APPLICATION_ENABLED: bool = False
    KNOWLEDGE_V2_CAPABILITY_PLANNER_ENABLED: bool = False
    KNOWLEDGE_V2_MULTI_INDEX_RETRIEVAL_ENABLED: bool = False
    KNOWLEDGE_V2_QUESTION_INDEX_ENABLED: bool = False
    KNOWLEDGE_V2_SUMMARY_INDEX_ENABLED: bool = False
    KNOWLEDGE_V2_GRAPH_INDEX_ENABLED: bool = False
    KNOWLEDGE_V2_GRAPH_RUNTIME_ENABLED: bool = False
    KNOWLEDGE_V2_SUMMARY_RUNTIME_ENABLED: bool = False
    KNOWLEDGE_V2_TOC_ENHANCE_ENABLED: bool = False
    KNOWLEDGE_V23_ARTIFACTS_ENABLED: bool = False
    KNOWLEDGE_V23_OUTLINE_ENABLED: bool = False
    KNOWLEDGE_V23_TABLE_ENABLED: bool = False
    KNOWLEDGE_V23_MODEL_REVISION_ENABLED: bool = True
    KNOWLEDGE_V23_TERM_EXPANSION_ENABLED: bool = False
    KNOWLEDGE_V23_LLM_PLANNER_ENABLED: bool = False
    KNOWLEDGE_V23_RRF_FUSION_ENABLED: bool = False
    KNOWLEDGE_V23_INCREMENTAL_BUILD_ENABLED: bool = False
    KNOWLEDGE_V23_QUALITY_ENABLED: bool = True
    KNOWLEDGE_V24_RELEASE_ENABLED: bool = False
    KNOWLEDGE_V24_FEDERATION_ENABLED: bool = False
    KNOWLEDGE_V24_ARTIFACT_ACL_ENABLED: bool = False
    KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS: int = 900
    KNOWLEDGE_RUNTIME_CAPABILITY_PROBE_ENABLED: bool = True
    KNOWLEDGE_RUNTIME_CAPABILITY_CACHE_SECONDS: int = 300
    KNOWLEDGE_TRANSLATION_ENABLED: bool = False
    KNOWLEDGE_TRANSLATION_ENGINE: str = "docutranslate"
    ARTIFACT_STORE_TYPE: str = "local"
    ARTIFACT_LOCAL_ROOT: str = "/data/knowledge-artifacts"
    KNOWLEDGE_BUILD_WORKER_CONCURRENCY: int = 2
    KNOWLEDGE_BUILD_LEASE_SECONDS: int = 120
    KNOWLEDGE_BUILD_MAX_ATTEMPTS: int = 3
    KNOWLEDGE_BUILD_RETRY_BACKOFF_SECONDS: int = 60
    KNOWLEDGE_TRANSLATION_WORKER_CONCURRENCY: int = 2
    KNOWLEDGE_TRANSLATION_LEASE_SECONDS: int = 120
    DOCUTRANSLATE_BASE_URL: str = "http://127.0.0.1:8010"
    DOCUTRANSLATE_TIMEOUT_SECONDS: float = 120.0
    MINERU_BASE_URL: str = "http://127.0.0.1:8020"
    MINERU_TIMEOUT_SECONDS: float = 120.0
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_TIMEOUT_SECONDS: float = 120.0
    OLLAMA_TRANSLATION_MODEL: str = "llama3"

    CORS_ORIGINS: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:3000"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


def parse_connector_fs_roots(raw: str | None = None) -> dict[str, str]:
    value = raw if raw is not None else settings.KNOWLEDGE_CONNECTOR_FS_ROOTS
    roots: dict[str, str] = {}
    for part in (value or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            continue
        alias, path = part.split("=", 1)
        alias = alias.strip()
        path = path.strip()
        if alias and path:
            roots[alias] = path
    return roots


def parse_private_network_allowlist(raw: str | None = None) -> set[str]:
    value = raw if raw is not None else settings.KNOWLEDGE_HTTP_PRIVATE_NETWORK_ALLOWLIST
    return {item.strip() for item in (value or "").split(",") if item.strip()}


settings = Settings()
