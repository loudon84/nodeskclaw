"""Pydantic schemas for Hermes Insight API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InsightWarningSchema(BaseModel):
    code: str
    message: str
    profile_name: str | None = None


class ContainerRuntimeSchema(BaseModel):
    container_name: str
    docker_status: str = "unknown"
    health: str = "unknown"
    cpu_percent: float | None = None
    memory_used_bytes: int | None = None
    memory_limit_bytes: int | None = None
    memory_percent: float | None = None
    disk_used_bytes: int | None = None
    disk_total_bytes: int | None = None
    disk_percent: float | None = None
    ports: list[str] = Field(default_factory=list)
    last_probe_at: str | None = None


class ProfileRuntimeDetailSchema(BaseModel):
    status: str = "unknown"
    api_server_enabled: bool = False
    api_server_port: int | None = None
    webui_port: int | None = None
    state_db_exists: bool = False
    config_exists: bool = False
    webui_index_exists: bool = False
    last_state_write_at: str | None = None
    last_session_at: str | None = None


class UsageSummarySchema(BaseModel):
    total_sessions: int = 0
    total_messages: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0


class ProfileInsightItemSchema(BaseModel):
    profile_name: str
    runtime: ProfileRuntimeDetailSchema
    usage: UsageSummarySchema


class DailyTokenItemSchema(BaseModel):
    date: str
    profile_name: str
    sessions: int = 0
    messages: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0


class ModelUsageItemSchema(BaseModel):
    profile_name: str
    model: str
    sessions: int = 0
    messages: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    session_share: float = 0.0
    token_share: float = 0.0
    cost_share: float = 0.0


class TokenBreakdownSchema(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class InsightResponseSchema(BaseModel):
    scope: str
    instance_id: str
    profile_name: str
    period_days: int = 30
    generated_at: str
    container: ContainerRuntimeSchema
    profiles: list[ProfileInsightItemSchema] = Field(default_factory=list)
    profile: ProfileInsightItemSchema | None = None
    usage: UsageSummarySchema
    daily_tokens: list[DailyTokenItemSchema] = Field(default_factory=list)
    models: list[ModelUsageItemSchema] = Field(default_factory=list)
    token_breakdown: TokenBreakdownSchema = Field(default_factory=TokenBreakdownSchema)
    warnings: list[InsightWarningSchema] = Field(default_factory=list)
