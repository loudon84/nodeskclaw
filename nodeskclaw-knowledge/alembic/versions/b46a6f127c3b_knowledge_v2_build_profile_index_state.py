"""knowledge_v2_build_profile_index_state

Revision ID: b46a6f127c3b
Revises: b604e2f980dd
Create Date: 2026-08-26 15:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b46a6f127c3b"
down_revision: str | None = "b604e2f980dd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_build_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_key", sa.String(length=64), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("index_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("trigger_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("runtime_hints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_build_profiles_org_id", "knowledge_build_profiles", ["org_id"])
    op.create_index("ix_knowledge_build_profiles_deleted_at", "knowledge_build_profiles", ["deleted_at"])
    op.create_index(
        "uq_build_profile_org_name",
        "knowledge_build_profiles",
        ["org_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_build_profile_system_key",
        "knowledge_build_profiles",
        ["system_key"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND system_key IS NOT NULL"),
    )

    op.create_table(
        "knowledge_index_states",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("index_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="not_built"),
        sa.Column("build_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_watermark", sa.String(length=64), nullable=True),
        sa.Column("last_build_job_id", sa.String(length=36), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("runtime_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_built_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_index_states_org_id", "knowledge_index_states", ["org_id"])
    op.create_index(
        "ix_knowledge_index_states_knowledge_base_id",
        "knowledge_index_states",
        ["knowledge_base_id"],
    )
    op.create_index("ix_knowledge_index_states_deleted_at", "knowledge_index_states", ["deleted_at"])
    op.create_index(
        "uq_index_state_kb_type",
        "knowledge_index_states",
        ["knowledge_base_id", "index_type"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_build_jobs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_base_id", sa.String(length=36), nullable=False),
        sa.Column("build_profile_id", sa.String(length=36), nullable=True),
        sa.Column("index_type", sa.String(length=64), nullable=False),
        sa.Column("trigger_reason", sa.String(length=64), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_token", sa.String(length=64), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stage_results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_build_jobs_org_id", "knowledge_build_jobs", ["org_id"])
    op.create_index(
        "ix_knowledge_build_jobs_knowledge_base_id",
        "knowledge_build_jobs",
        ["knowledge_base_id"],
    )
    op.create_index("ix_knowledge_build_jobs_index_type", "knowledge_build_jobs", ["index_type"])
    op.create_index("ix_knowledge_build_jobs_status", "knowledge_build_jobs", ["status"])
    op.create_index("ix_knowledge_build_jobs_deleted_at", "knowledge_build_jobs", ["deleted_at"])
    op.create_index(
        "uq_build_job_active_kb_index",
        "knowledge_build_jobs",
        ["knowledge_base_id", "index_type"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status IN ('queued', 'running')"),
    )


def downgrade() -> None:
    op.drop_index("uq_build_job_active_kb_index", table_name="knowledge_build_jobs")
    op.drop_index("ix_knowledge_build_jobs_deleted_at", table_name="knowledge_build_jobs")
    op.drop_index("ix_knowledge_build_jobs_status", table_name="knowledge_build_jobs")
    op.drop_index("ix_knowledge_build_jobs_index_type", table_name="knowledge_build_jobs")
    op.drop_index("ix_knowledge_build_jobs_knowledge_base_id", table_name="knowledge_build_jobs")
    op.drop_index("ix_knowledge_build_jobs_org_id", table_name="knowledge_build_jobs")
    op.drop_table("knowledge_build_jobs")

    op.drop_index("uq_index_state_kb_type", table_name="knowledge_index_states")
    op.drop_index("ix_knowledge_index_states_deleted_at", table_name="knowledge_index_states")
    op.drop_index("ix_knowledge_index_states_knowledge_base_id", table_name="knowledge_index_states")
    op.drop_index("ix_knowledge_index_states_org_id", table_name="knowledge_index_states")
    op.drop_table("knowledge_index_states")

    op.drop_index("uq_build_profile_system_key", table_name="knowledge_build_profiles")
    op.drop_index("uq_build_profile_org_name", table_name="knowledge_build_profiles")
    op.drop_index("ix_knowledge_build_profiles_deleted_at", table_name="knowledge_build_profiles")
    op.drop_index("ix_knowledge_build_profiles_org_id", table_name="knowledge_build_profiles")
    op.drop_table("knowledge_build_profiles")
