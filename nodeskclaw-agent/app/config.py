from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://nodeskclaw:nodeskclaw@localhost:5432/nodeskclaw"
    SKILL_AGENT_INTERNAL_TOKEN: str = "change-me-skill-agent-token"
    SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS: str = ""
    SKILL_AGENT_WORKER_ENABLED: bool = True
    SKILL_AGENT_WORKER_INTERVAL_SECONDS: float = 1.0
    SKILL_AGENT_LEASE_SECONDS: int = 60
    SKILL_AGENT_SCHEMA: str = "agent"
    SKILL_AGENT_ARTIFACT_DIR: str = "./data/skill-agent-artifacts"
    SKILL_AGENT_STORAGE_DRIVER: str = "local"
    SKILL_AGENT_S3_ENDPOINT: str = ""
    SKILL_AGENT_S3_BUCKET: str = "nodeskclaw-artifacts"
    SKILL_AGENT_S3_ACCESS_KEY: str = ""
    SKILL_AGENT_S3_SECRET_KEY: str = ""
    SKILL_AGENT_S3_REGION: str = "auto"
    SKILL_AGENT_ROLE: str = "central"
    SKILL_AGENT_EDGE_TOKEN: str = ""
    SKILL_AGENT_EDGE_NODE_ID: str = ""
    SKILL_AGENT_CENTRAL_BASE_URL: str = "http://localhost:4510"
    SKILL_AGENT_SECRET_STORE: str = "./.skill-agent-secrets"
    SKILL_AGENT_EDGE_POLL_SECONDS: float = 2.0
    SKILL_AGENT_INSECURE_MODE: bool = False


settings = Settings()
