"""v241_channel_event_build_job_nullable

Revision ID: d0e41dc0d166
Revises: 07548d9f3803
Create Date: 2026-08-28 16:46:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d0e41dc0d166"
down_revision: str | None = "07548d9f3803"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_release_channel_events",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("from_release_id", sa.String(length=36), nullable=True),
        sa.Column("to_release_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("actor_member_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_release_channel_events_application_id"),
        "knowledge_release_channel_events",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_release_channel_events_deleted_at"),
        "knowledge_release_channel_events",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_release_channel_events_org_id"),
        "knowledge_release_channel_events",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "ix_release_channel_event_app_channel",
        "knowledge_release_channel_events",
        ["application_id", "channel"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.add_column(
        "knowledge_application_releases",
        sa.Column("manifest_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "knowledge_application_releases",
        sa.Column("validation_job_id", sa.String(length=36), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE knowledge_application_releases "
            "SET status = 'validated' "
            "WHERE status IN ('promoted', 'superseded') AND deleted_at IS NULL"
        )
    )

    op.alter_column(
        "knowledge_build_jobs",
        "knowledge_base_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )
    op.drop_index("uq_build_job_active_kb_index", table_name="knowledge_build_jobs")
    op.create_index(
        "uq_build_job_active_kb_index",
        "knowledge_build_jobs",
        ["knowledge_base_id", "index_type"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND knowledge_base_id IS NOT NULL "
            "AND status IN ('queued', 'running')"
        ),
    )
    op.create_index(
        "uq_build_job_active_release_validation",
        "knowledge_build_jobs",
        ["release_candidate_id"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND target_kind = 'release_validation' "
            "AND release_candidate_id IS NOT NULL "
            "AND status IN ('queued', 'running')"
        ),
    )


def downgrade() -> None:
    op.drop_index("uq_build_job_active_release_validation", table_name="knowledge_build_jobs")
    op.drop_index("uq_build_job_active_kb_index", table_name="knowledge_build_jobs")
    op.create_index(
        "uq_build_job_active_kb_index",
        "knowledge_build_jobs",
        ["knowledge_base_id", "index_type"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status IN ('queued', 'running')"),
    )
    op.alter_column(
        "knowledge_build_jobs",
        "knowledge_base_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )
    op.drop_column("knowledge_application_releases", "validation_job_id")
    op.drop_column("knowledge_application_releases", "manifest_hash")
    op.drop_index("ix_release_channel_event_app_channel", table_name="knowledge_release_channel_events")
    op.drop_index(op.f("ix_knowledge_release_channel_events_org_id"), table_name="knowledge_release_channel_events")
    op.drop_index(
        op.f("ix_knowledge_release_channel_events_deleted_at"),
        table_name="knowledge_release_channel_events",
    )
    op.drop_index(
        op.f("ix_knowledge_release_channel_events_application_id"),
        table_name="knowledge_release_channel_events",
    )
    op.drop_table("knowledge_release_channel_events")
