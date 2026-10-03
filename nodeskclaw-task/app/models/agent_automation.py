from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class AgentAutomation(BaseModel):
    __tablename__ = "agent_automations"
    __table_args__ = (
        Index(
            "ix_agent_automations_tenant_status",
            "tenant_id",
            "status",
        ),
        Index(
            "ix_agent_automations_tenant_owner",
            "tenant_id",
            "owner_user_id",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_user_id: Mapped[str] = mapped_column(String(36), nullable=False)
    agent_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)
    generation: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    input_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    knowledge_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    connector_binding_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    integration_account_refs: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    manual_run_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    concurrency_policy: Mapped[str] = mapped_column(
        String(32), default="SKIP_IF_RUNNING", nullable=False
    )
    max_concurrent_runs: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)


class AutomationTrigger(BaseModel):
    __tablename__ = "automation_triggers"
    __table_args__ = (
        Index("ix_automation_triggers_next_fire", "status", "next_fire_at"),
        Index(
            "uq_automation_triggers_automation_type",
            "automation_id",
            "trigger_type",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND trigger_type = 'CRON'"),
        ),
    )

    automation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="DISABLED", nullable=False)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cron_expr: Mapped[str | None] = mapped_column(String(128), nullable=True)
    webhook_secret_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    webhook_key_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    prompt_mapping: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    last_fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_fire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AutomationInvocation(BaseModel):
    __tablename__ = "automation_invocations"
    __table_args__ = (
        Index(
            "uq_automation_invocations_idempotency",
            "automation_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_automation_invocations_webhook_event",
            "trigger_id",
            "source_event_id",
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL AND trigger_id IS NOT NULL AND source_event_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_automation_invocations_cron_fire",
            "trigger_id",
            "scheduled_fire_at",
            unique=True,
            postgresql_where=text(
                "deleted_at IS NULL AND trigger_id IS NOT NULL AND scheduled_fire_at IS NOT NULL"
            ),
        ),
        Index("ix_automation_invocations_status", "status"),
    )

    automation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    automation_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_event_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    scheduled_fire_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    owner_user_id_snapshot: Mapped[str] = mapped_column(String(36), nullable=False)
    input_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    input_payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    rendered_prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    rendered_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), default="RECEIVED", nullable=False)
    remote_agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    remote_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cancel_requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RemoteAgentDispatchJob(BaseModel):
    __tablename__ = "remote_agent_dispatch_jobs"
    __table_args__ = (
        Index(
            "uq_remote_agent_dispatch_jobs_invocation",
            "invocation_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_remote_agent_dispatch_jobs_ready",
            "status",
            "next_attempt_at",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    invocation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    automation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    remote_agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class AutomationWebhookNonce(BaseModel):
    __tablename__ = "automation_webhook_nonces"
    __table_args__ = (
        Index(
            "uq_automation_webhook_nonces_trigger_nonce",
            "trigger_id",
            "nonce",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("ix_automation_webhook_nonces_expires", "expires_at"),
    )

    trigger_id: Mapped[str] = mapped_column(String(36), nullable=False)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
