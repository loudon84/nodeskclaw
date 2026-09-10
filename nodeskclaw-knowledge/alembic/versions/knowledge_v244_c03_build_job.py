"""knowledge_v244_c03_build_job

Revision ID: 0e3836519746
Revises: d0e41dc0d166
Create Date: 2026-09-11 16:41:25.802922

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0e3836519746"
down_revision: str | None = "d0e41dc0d166"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_build_jobs", sa.Column("scope_type", sa.String(length=32), nullable=True))
    op.add_column("knowledge_build_jobs", sa.Column("scope_id", sa.String(length=36), nullable=True))
    op.alter_column(
        "knowledge_build_jobs",
        "index_type",
        existing_type=sa.VARCHAR(length=64),
        nullable=True,
    )
    op.create_index(op.f("ix_knowledge_build_jobs_scope_id"), "knowledge_build_jobs", ["scope_id"], unique=False)
    op.drop_index("uq_build_job_active_kb_index", table_name="knowledge_build_jobs")
    op.create_index(
        "uq_build_job_active_kb_index",
        "knowledge_build_jobs",
        ["knowledge_base_id", "index_type"],
        unique=True,
        postgresql_where=sa.text(
            "deleted_at IS NULL AND knowledge_base_id IS NOT NULL "
            "AND index_type IS NOT NULL "
            "AND status IN ('queued', 'running')"
        ),
    )


def downgrade() -> None:
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
    op.drop_index(op.f("ix_knowledge_build_jobs_scope_id"), table_name="knowledge_build_jobs")
    op.alter_column(
        "knowledge_build_jobs",
        "index_type",
        existing_type=sa.VARCHAR(length=64),
        nullable=False,
    )
    op.drop_column("knowledge_build_jobs", "scope_id")
    op.drop_column("knowledge_build_jobs", "scope_type")
