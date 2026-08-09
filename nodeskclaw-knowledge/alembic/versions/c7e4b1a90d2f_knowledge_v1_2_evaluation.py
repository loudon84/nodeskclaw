"""knowledge v1.2 evaluation tables

Revision ID: c7e4b1a90d2f
Revises: fd64182b8bad
Create Date: 2026-08-09 09:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7e4b1a90d2f"
down_revision: str | None = "fd64182b8bad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_evaluation_sets",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_set_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_evaluation_sets_org_id", "knowledge_evaluation_sets", ["org_id"])
    op.create_index(
        "ix_knowledge_evaluation_sets_knowledge_set_id",
        "knowledge_evaluation_sets",
        ["knowledge_set_id"],
    )
    op.create_index("ix_knowledge_evaluation_sets_deleted_at", "knowledge_evaluation_sets", ["deleted_at"])

    op.create_table(
        "knowledge_evaluation_cases",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("evaluation_set_id", sa.String(length=36), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column(
            "expected_source_file_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("expected_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expected_answer", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_evaluation_cases_evaluation_set_id",
        "knowledge_evaluation_cases",
        ["evaluation_set_id"],
    )
    op.create_index("ix_knowledge_evaluation_cases_deleted_at", "knowledge_evaluation_cases", ["deleted_at"])

    op.create_table(
        "knowledge_evaluation_runs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("evaluation_set_id", sa.String(length=36), nullable=False),
        sa.Column("retrieval_profile_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_knowledge_evaluation_runs_evaluation_set_id",
        "knowledge_evaluation_runs",
        ["evaluation_set_id"],
    )
    op.create_index(
        "ix_knowledge_evaluation_runs_retrieval_profile_id",
        "knowledge_evaluation_runs",
        ["retrieval_profile_id"],
    )
    op.create_index("ix_knowledge_evaluation_runs_status", "knowledge_evaluation_runs", ["status"])
    op.create_index("ix_knowledge_evaluation_runs_deleted_at", "knowledge_evaluation_runs", ["deleted_at"])

    op.create_table(
        "knowledge_evaluation_results",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("case_id", sa.String(length=36), nullable=False),
        sa.Column("hit_at_k", sa.Float(), nullable=False, server_default="0"),
        sa.Column("recall_at_k", sa.Float(), nullable=False, server_default="0"),
        sa.Column("mrr", sa.Float(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "returned_source_file_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("unauthorized_hit", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_knowledge_evaluation_results_run_id", "knowledge_evaluation_results", ["run_id"])
    op.create_index("ix_knowledge_evaluation_results_case_id", "knowledge_evaluation_results", ["case_id"])
    op.create_index("ix_knowledge_evaluation_results_deleted_at", "knowledge_evaluation_results", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_evaluation_results_deleted_at", table_name="knowledge_evaluation_results")
    op.drop_index("ix_knowledge_evaluation_results_case_id", table_name="knowledge_evaluation_results")
    op.drop_index("ix_knowledge_evaluation_results_run_id", table_name="knowledge_evaluation_results")
    op.drop_table("knowledge_evaluation_results")

    op.drop_index("ix_knowledge_evaluation_runs_deleted_at", table_name="knowledge_evaluation_runs")
    op.drop_index("ix_knowledge_evaluation_runs_status", table_name="knowledge_evaluation_runs")
    op.drop_index("ix_knowledge_evaluation_runs_retrieval_profile_id", table_name="knowledge_evaluation_runs")
    op.drop_index("ix_knowledge_evaluation_runs_evaluation_set_id", table_name="knowledge_evaluation_runs")
    op.drop_table("knowledge_evaluation_runs")

    op.drop_index("ix_knowledge_evaluation_cases_deleted_at", table_name="knowledge_evaluation_cases")
    op.drop_index("ix_knowledge_evaluation_cases_evaluation_set_id", table_name="knowledge_evaluation_cases")
    op.drop_table("knowledge_evaluation_cases")

    op.drop_index("ix_knowledge_evaluation_sets_deleted_at", table_name="knowledge_evaluation_sets")
    op.drop_index("ix_knowledge_evaluation_sets_knowledge_set_id", table_name="knowledge_evaluation_sets")
    op.drop_index("ix_knowledge_evaluation_sets_org_id", table_name="knowledge_evaluation_sets")
    op.drop_table("knowledge_evaluation_sets")
