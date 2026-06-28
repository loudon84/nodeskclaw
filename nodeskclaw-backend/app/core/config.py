"""Application settings loaded from environment variables."""

import logging
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger(__name__)

_K8S_NS_FILE = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")


def _detect_platform_namespace() -> str:
    try:
        return _K8S_NS_FILE.read_text().strip()
    except (FileNotFoundError, PermissionError):
        return "nodeskclaw-system"


def _qualify_k8s_service_url(url: str, service_name: str, namespace: str) -> str:
    normalized = url.rstrip("/")
    parsed = urlsplit(normalized)
    if parsed.hostname != service_name:
        return normalized

    namespace = namespace.strip()
    if not namespace:
        return normalized

    host = f"{service_name}.{namespace}.svc.cluster.local"
    netloc = f"{host}:{parsed.port}" if parsed.port else host
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)).rstrip("/")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── App ──────────────────────────────────────────────
    APP_NAME: str = "NoDeskClaw"
    APP_VERSION: str = "dev"
    DEBUG: bool = False
    LOG_SQL: bool = False
    LOG_HEALTH_CHECK: bool = False

    # ── Database ─────────────────────────────────────────
    DATABASE_URL: str = ""  # PostgreSQL，从 .env 读取
    DATABASE_NAME_SUFFIX: str = ""  # auto = 用本机 hostname，留空 = 使用 DATABASE_URL 原始库名
    DB_POOL_SIZE: int = 10
    DB_POOL_MAX_OVERFLOW: int = 20

    @model_validator(mode="after")
    def _resolve_database_url(self) -> "Settings":
        if not self.DATABASE_NAME_SUFFIX:
            return self
        suffix = self.DATABASE_NAME_SUFFIX
        if suffix == "auto":
            raw = socket.gethostname()
            suffix = re.sub(r"[^a-z0-9]", "_", raw.lower()).strip("_")
            suffix = re.sub(r"_local$", "", suffix)
            suffix = re.sub(r"_+", "_", suffix)
            suffix = suffix[:40]
        base_url, sep, db_name = self.DATABASE_URL.rpartition("/")
        if sep:
            self.DATABASE_URL = f"{base_url}/{db_name}_{suffix}"
        return self

    _INSECURE_DEFAULTS = frozenset({
        "change-me-in-production",
        "change-me-32-bytes-base64-key__=",
    })

    @model_validator(mode="after")
    def _check_insecure_defaults(self) -> "Settings":
        if self.DEBUG:
            return self
        issues: list[str] = []
        if self.JWT_SECRET in self._INSECURE_DEFAULTS:
            issues.append("JWT_SECRET")
        if self.ENCRYPTION_KEY in self._INSECURE_DEFAULTS:
            issues.append("ENCRYPTION_KEY")
        if issues:
            msg = (
                f"{', '.join(issues)} 仍为默认值，生产环境存在严重安全风险。"
                " 请在 .env 中设置安全的随机值。"
            )
            raise ValueError(msg)
        return self

    # ── JWT ──────────────────────────────────────────────
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # ── 登录安全 ─────────────────────────────────────────
    LOGIN_EMAIL_WHITELIST: str = ""  # 逗号分隔的域名列表，为空则不限制

    # ── CE 超管 ──────────────────────────────────────────
    INIT_ADMIN_ACCOUNT: str = "admin"  # 默认超管 username，留空则跳过自动创建
    RESET_ADMIN_PASSWORD: bool = False  # 设为 True 后重启强制重置超管密码

    # ── EE 平台管理员 ─────────────────────────────────────
    INIT_EE_ADMIN_ACCOUNT: str = "deskclaw-admin"  # EE Admin 后台管理员 username，留空则跳过
    RESET_EE_ADMIN_PASSWORD: bool = False  # 设为 True 后重启强制重置 EE 管理员密码

    # ── Encryption (AES-256-GCM for KubeConfig) ─────────
    ENCRYPTION_KEY: str = "change-me-32-bytes-base64-key__="

    # ── 飞书 SSO（Portal 应用，可选） ─────────────────────
    FEISHU_APP_ID_PORTAL: str = ""
    FEISHU_APP_SECRET_PORTAL: str = ""

    # ── Portal ────────────────────────────────────────────
    PORTAL_BASE_URL: str = ""  # 用户门户基础 URL，如 https://portal.example.com

    # ── 云平台 ──────────────────────────────────────────
    VKE_SUBNET_ID: str = ""

    # ── LLM Proxy ─────────────────────────────────────────
    NODESKCLAW_WEBHOOK_BASE_URL: str = ""  # AI 员工回调后端的基础地址，如 http://nodeskclaw-backend:4510
    NODESKCLAW_HOST: str = ""  # 外部可达域名，如 https://nodeskclaw.example.com（废弃，保留兼容）
    LLM_PROXY_URL: str = ""  # 独立 LLM Proxy 服务外部地址，如 https://llm-proxy.example.com
    LLM_PROXY_INTERNAL_URL: str = ""  # K8s 集群内网地址，用于 openclaw.json 中的 baseUrl（绕过 ALB）
    LLM_ATTRIBUTION_SECRET: str = ""  # LLM 用量归属签名密钥，后端和 LLM Proxy 保持一致

    @model_validator(mode="after")
    def _qualify_llm_proxy_internal_url(self) -> "Settings":
        if self.LLM_PROXY_INTERNAL_URL:
            self.LLM_PROXY_INTERNAL_URL = _qualify_k8s_service_url(
                self.LLM_PROXY_INTERNAL_URL,
                "nodeskclaw-llm-proxy",
                self.PLATFORM_NAMESPACE,
            )
        return self

    # ── Agent API（AI 员工 Pod 回调后端的内网地址）────────
    AGENT_API_BASE_URL: str = "http://localhost:4510/api/v1"
    AGENT_FILE_DOWNLOAD_BASE_URL: str = ""
    GENE_CALLBACK_SECRET: str = ""
    ALLOW_LEGACY_GENE_CALLBACKS: bool = False

    # ── Agent Tunnel（实例通过 WebSocket 主动连接后端的地址）────
    TUNNEL_BASE_URL: str = ""

    # ── 出站代理（用于访问 OpenAI/Anthropic 等外部 API）────
    HTTPS_PROXY: str = ""

    # ── Platform Namespace（AI 员工 Pod NetworkPolicy 允许访问的后端命名空间）──
    PLATFORM_NAMESPACE: str = _detect_platform_namespace()

    # ── Gene Seed ───────────────────────────────────────
    SEED_GENES: bool = True

    # ── Skill Registries ─────────────────────────────────
    # JSON array of registry configs:
    # [{"type":"deskhub","id":"deskhub","url":"https://skills.deskclaw.me","api_key":"","name":"DeskHub"},
    #  {"type":"clawhub","id":"clawhub","url":"https://clawhub.ai","api_key":"","name":"ClawHub"}]
    SKILL_REGISTRIES: str = ""

    # Non-empty value auto-registers as type=deskhub, id=deskhub adapter
    DESKHUB_REGISTRY_URL: str = ""
    DESKHUB_API_KEY: str = ""
    DESKHUB_WEB_URL: str = ""

    # ── GeneHub Desktop ──────────────────────────────────
    GENEHUB_BUNDLE_SIGNING_SECRET: str = ""
    GENEHUB_BUNDLE_SIGNATURE_ENABLED: bool = True
    GENEHUB_DESKTOP_SYNC_ENABLED: bool = True
    GENEHUB_REGISTRY_NAME: str = "Enterprise GeneHub Registry"
    GENEHUB_API_PREFIX: str = "/api/v1/desktop"
    GENEHUB_HEALTH_ENDPOINT: str = "/api/v1/desktop/genehub/health"
    GENEHUB_REQUIRES_AUTH: bool = True

    # ── S3 兼容对象存储 ─────────────────────────────────
    S3_ENDPOINT: str = ""
    S3_REGION: str = ""
    S3_BUCKET: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_KEY_PREFIX: str = ""

    # ── 本地文件存储（S3 未配置时自动启用）─────────────────
    LOCAL_STORAGE_DIR: str = ""

    # ── 文件上传策略 ─────────────────────────────────────
    UPLOAD_STORAGE_BACKEND: str = "auto"
    UPLOAD_GATEWAY_PROXY_BODY_SIZE_MB: int = 50
    UPLOAD_PROXY_READ_TIMEOUT_SECONDS: int = 300
    UPLOAD_PROXY_SEND_TIMEOUT_SECONDS: int = 300
    UPLOAD_CHAT_ATTACHMENT_MAX_MB: int = 20
    UPLOAD_CHAT_ATTACHMENT_MAX_COUNT: int = 5
    UPLOAD_CHAT_ATTACHMENT_RETENTION_DAYS: int = 90
    UPLOAD_SHARED_FILE_MAX_MB: int = 200
    UPLOAD_LARGE_FILE_MAX_MB: int = 2048
    UPLOAD_CHUNKED_UPLOAD_THRESHOLD_MB: int = 50
    UPLOAD_CHUNK_SIZE_MB: int = 8
    UPLOAD_WORKSPACE_QUOTA_MB: int = 10240
    UPLOAD_BLOCKED_EXTENSIONS: str = ".exe,.bat,.cmd,.sh"
    UPLOAD_ALLOWED_CONTENT_TYPES: str = ""
    UPLOAD_SECURITY_SCAN_MODE: str = "metadata_only"
    UPLOAD_SCANNER_PROVIDER: str = "none"
    UPLOAD_SCANNER_ENDPOINT: str = ""
    UPLOAD_SCANNER_TIMEOUT_SECONDS: int = 60
    UPLOAD_SCANNER_MAX_RETRIES: int = 3
    UPLOAD_SCANNER_MAX_FILE_MB: int = 2048
    UPLOAD_SCANNER_FAIL_CLOSED: bool = True

    # ── 匿名安装遥测（CE-only）─────────────────────────────
    TELEMETRY_ENABLED: bool = True
    POSTHOG_HOST: str = "https://us.i.posthog.com"
    POSTHOG_API_KEY: str = "phc_qdVoTVCcHEzgwhZVwtPuu6BeoTJPGNQskeUBcXVxnxuF"

    # ── CORS ─────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:4517", "http://localhost:4518"]

    # ── Gateway ──────────────────────────────────────────
    GATEWAY_HEALTH_CHECK_INTERVAL: int = 10
    GATEWAY_HEALTH_CHECK_TIMEOUT: int = 5
    GATEWAY_FAILURE_THRESHOLD: int = 3
    GATEWAY_RECOVERY_THRESHOLD: int = 2
    GATEWAY_TOOL_CACHE_TTL: int = 60
    GATEWAY_SSE_IDLE_TIMEOUT: int = 300
    GATEWAY_SSE_HEARTBEAT_INTERVAL: int = 30
    GATEWAY_SSE_RECONNECT_ATTEMPTS: int = 3
    GATEWAY_DEFAULT_TIMEOUT: int = 30
    GATEWAY_AUDIT_RETENTION_DAYS: int = 90
    GATEWAY_MAX_REQUEST_BODY_BYTES: int = 1048576
    GATEWAY_GLOBAL_RATE_LIMIT_RPM: int = 500
    GATEWAY_SSE_MAX_CONNECTIONS: int = 500
    GATEWAY_SSE_MAX_CONNECTIONS_PER_INSTANCE: int = 100
    GATEWAY_ORIGIN_CHECK_MODE: str = "relaxed"
    GATEWAY_UPSTREAM_HOST_WHITELIST: str = ""
    GATEWAY_API_KEY_PREFIX: str = "mcp_"

    # ── Hermes Skill Hub ─────────────────────────────────
    HERMES_SKILL_HUB_ROOT: str = "/data/nodeskclaw/skills"
    HERMES_SKILL_SCAN_MAX_DEPTH: int = 4
    HERMES_SKILL_SCAN_TIMEOUT_SECONDS: int = 30
    HERMES_SKILL_IMPORT_MAX_SIZE_MB: int = 50
    HERMES_SKILL_REGISTRY_SYNC_TIMEOUT_SECONDS: int = 60

    # ── Hermes Docker Agent Bind (v4.4) ───────────────────
    HERMES_INSTANCES_ROOT: str = ""
    HERMES_DEFAULT_GATEWAY_INTERNAL_PORT: int = 8642
    HERMES_AGENT_HOST_IP: str = ""
    HERMES_GATEWAY_PROBE_TIMEOUT_SECONDS: int = 3
    HERMES_GATEWAY_PROBE_CONCURRENCY: int = 5
    HERMES_AUTO_PROBE_AFTER_SCAN: bool = True

    # ── Hermes API Server Gateway (v4.4.1 hotfix) ──────────
    HERMES_DEFAULT_API_SERVER_PORT: int = 8642
    HERMES_API_SERVER_PROBE_TIMEOUT_SECONDS: int = 5
    HERMES_API_SERVER_CALL_TIMEOUT_SECONDS: int = 120
    HERMES_API_SERVER_PROBE_CONCURRENCY: int = 5
    HERMES_ENABLE_CALL_TEST: bool = False
    HERMES_PREFER_RUNS_API: bool = True
    HERMES_RESTART_WAIT_TIMEOUT_SECONDS: int = 60
    HERMES_RESTART_POLL_INTERVAL_SECONDS: int = 3
    HERMES_GIT_ALLOWED_HOSTS: str = ""

    # ── Hermes Agent Adapter ──────────────────────────────
    HERMES_AGENT_DEFAULT_TIMEOUT_SECONDS: int = 900
    HERMES_AGENT_CONNECT_TIMEOUT_SECONDS: int = 10
    HERMES_AGENT_READ_TIMEOUT_SECONDS: int = 60

    # ── Hermes Task Worker ────────────────────────────────
    HERMES_TASK_WORKER_ENABLED: bool = True
    HERMES_TASK_WORKER_INTERVAL_SECONDS: int = 2
    HERMES_TASK_WORKER_BATCH_SIZE: int = 5
    HERMES_TASK_DEFAULT_TIMEOUT_SECONDS: int = 900
    HERMES_TASK_LOCK_TIMEOUT_SECONDS: int = 300
    HERMES_TASK_SSE_HEARTBEAT_SECONDS: int = 30

    MCP_TASK_TOOLS_ENABLED: bool = True
    MCP_TASK_SSE_ENABLED: bool = True
    MCP_TASK_SSE_TOKEN_TTL_SECONDS: int = 900
    MCP_TASK_SSE_INCLUDE_RESULT_ON_COMPLETE: bool = True
    MCP_TASK_DEFAULT_EXECUTION_MODE: str = "async_event"
    MCP_TASK_WAIT_ENABLED: bool = True
    MCP_TASK_WAIT_TIMEOUT_SECONDS: int = 900
    MCP_TASK_WAIT_DEFAULT_MODE: str = "queued"
    MCP_TASK_WAIT_POLL_INTERVAL_SECONDS: int = 3
    MCP_TASK_WAIT_MAX_TIMEOUT_SECONDS: int = 900
    MCP_TASK_WAIT_MAX_SECONDS: int = 300
    MCP_TASK_WAIT_FOR_MCP_CLIENT_TOKEN: bool = False
    MCP_TASK_WAIT_FOR_USER_JWT: bool = False
    MCP_TASK_WAIT_RETURN_TIMELINE: bool = True
    MCP_TASK_WAIT_RETURN_ARTIFACTS: bool = True
    MCP_TASK_WAIT_INCLUDE_PRIMARY_PREVIEW: bool = False
    MCP_TASK_PREVIEW_MAX_CHARS: int = 50000
    MCP_TASK_DEDUP_ENABLED: bool = True
    MCP_TASK_DEDUP_WINDOW_SECONDS: int = 600

    HERMES_QUEUE_ORG_MAX_QUEUED: int = 1000
    HERMES_QUEUE_USER_MAX_RUNNING: int = 3
    HERMES_QUEUE_SKILL_MAX_RUNNING: int = 10
    HERMES_QUEUE_AGENT_MAX_RUNNING: int = 5
    HERMES_QUEUE_DEFAULT_PRIORITY: int = 0
    HERMES_TASK_DEFAULT_MAX_RETRY: int = 1
    HERMES_TASK_RETRY_BACKOFF_SECONDS: int = 60

    # ── Hermes Artifact ───────────────────────────────────
    HERMES_OUTPUT_BASE_DIR_NAME: str = ".nodeskclaw"
    HERMES_WORKSPACE_ROOT: str = ""
    HERMES_ARTIFACT_MAX_SIZE_MB: int = 500
    HERMES_ARTIFACT_BATCH_DOWNLOAD_MAX_SIZE_MB: int = 1024
    HERMES_ARTIFACT_DISCOVERY_ENABLED: bool = True
    HERMES_ARTIFACT_DISCOVERY_CONTAINER_WORKSPACE_ROOT: str = "/data/hermes/workspace"
    HERMES_ARTIFACT_DISCOVERY_MAX_FILE_SIZE_MB: int = 200
    HERMES_ARTIFACT_DISCOVERY_ENABLE_MTIME_FALLBACK: bool = False
    HERMES_ARTIFACT_DISCOVERY_MTIME_WINDOW_SECONDS: int = 60
    HERMES_ARTIFACT_PROMOTE_DISCOVERED_ENABLED: bool = True
    HERMES_ARTIFACT_MATERIALIZE_FALLBACK_ENABLED: bool = True
    HERMES_ARTIFACT_PROMOTE_MODE: str = "all_documents"

    EXPERT_HEALTH_CACHE_TTL: int = 30
    EXPERT_RESPONSE_PREVIEW_MAX_CHARS: int = 4000
    EXPERT_UPSTREAM_TIMEOUT_SECONDS: int = 900
    EXPERT_EVENT_TOKEN_TTL_SECONDS: int = 7200

    # ── Hermes WebUI Expert ───────────────────────────────
    HERMES_EXPERT_DEFAULT_IMAGE: str = ""
    HERMES_AGENT_REPO: str = ""
    HERMES_AGENT_REF: str = "main"
    HERMES_WEBUI_REPO: str = ""
    HERMES_WEBUI_REF: str = "main"
    HERMES_WEBUI_BASE_IMAGE: str = ""
    HERMES_EXPERT_IMAGE: str = ""
    HERMES_EXPERT_IMAGE_REGISTRY: str = ""
    HERMES_EXPERT_DEFAULT_HINDSIGHT_API_URL: str = ""
    HERMES_EXPERT_DEFAULT_BIND_HOST: str = "0.0.0.0"
    HERMES_EXPERT_PORT_START: int = 8787
    HERMES_EXPERT_PORT_END: int = 8899
    HERMES_EXPERT_DATA_ROOT: str = ""
    PRIVATE_GIT_USERNAME: str = ""
    PRIVATE_GIT_TOKEN_SECRET: str = ""
    PRIVATE_REGISTRY_URL: str = ""
    PRIVATE_REGISTRY_USERNAME: str = ""
    PRIVATE_REGISTRY_PASSWORD_SECRET: str = ""

    # -- Docker 相关配置 ─────────────────────────────────────
    DOCKER_DATA_DIR: str = ""
    DOCKER_HOST_DATA_DIR: str = ""
    DOCKER_ATTACH_SCAN_DIRS: str = ""
    DOCKER_PUBLIC_HOST: str = ""
    DOCKER_PUBLIC_SCHEME: str = "http"
    DOCKER_COMPOSE_FILE: str = ""

settings = Settings()


def _strip_api_path(base_url: str) -> str:
    parsed = urlsplit(base_url.rstrip("/"))
    if not parsed.scheme or not parsed.netloc:
        return base_url.rstrip("/")
    path = parsed.path.rstrip("/")
    for suffix in ("/api/v1", "/api"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
            break
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def _normalize_api_v1_base_url(base_url: str) -> str:
    stripped = _strip_api_path(base_url)
    return f"{stripped}/api/v1" if stripped else ""


def get_nodeskclaw_webhook_base_url(cfg: Settings | None = None) -> str:
    active_settings = cfg or settings
    candidates = [
        getattr(active_settings, "NODESKCLAW_WEBHOOK_BASE_URL", ""),
        getattr(active_settings, "NODESKCLAW_HOST", ""),
        _strip_api_path(getattr(active_settings, "AGENT_API_BASE_URL", "")),
    ]
    for candidate in candidates:
        normalized = candidate.rstrip("/") if candidate else ""
        if normalized:
            return normalized
    return ""


def get_agent_file_download_base_url(cfg: Settings | None = None) -> str:
    active_settings = cfg or settings
    base_url = (
        getattr(active_settings, "AGENT_FILE_DOWNLOAD_BASE_URL", "")
        or getattr(active_settings, "AGENT_API_BASE_URL", "")
    )
    return _normalize_api_v1_base_url(base_url)
