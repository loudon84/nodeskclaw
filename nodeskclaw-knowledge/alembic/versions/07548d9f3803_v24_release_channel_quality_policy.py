"""v24_release_channel_quality_policy

Revision ID: 07548d9f3803
Revises: 14bcac212b54
Create Date: 2026-08-28 11:54:14.968601

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "07548d9f3803"
down_revision: str | None = "14bcac212b54"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_application_releases",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("release_manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("quality_snapshot_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_error", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_application_releases_application_id"),
        "knowledge_application_releases",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_application_releases_deleted_at"),
        "knowledge_application_releases",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_application_releases_org_id"),
        "knowledge_application_releases",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "uq_application_release_version",
        "knowledge_application_releases",
        ["application_id", "version"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_release_channels",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("active_release_id", sa.String(length=36), nullable=True),
        sa.Column("traffic_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("updated_by_member_id", sa.String(length=36), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_release_channels_application_id"),
        "knowledge_release_channels",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_release_channels_deleted_at"),
        "knowledge_release_channels",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_release_channels_org_id"),
        "knowledge_release_channels",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "uq_release_channel_app_name",
        "knowledge_release_channels",
        ["application_id", "channel"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_quality_snapshots",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_id", sa.String(length=36), nullable=False),
        sa.Column("manifest_hash", sa.String(length=64), nullable=True),
        sa.Column("release_id", sa.String(length=36), nullable=True),
        sa.Column("subscores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("coverage", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("overall_status", sa.String(length=32), nullable=False),
        sa.Column("gate_result", sa.String(length=16), nullable=True),
        sa.Column("gate_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_quality_snapshots_deleted_at"),
        "knowledge_quality_snapshots",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_quality_snapshots_org_id"),
        "knowledge_quality_snapshots",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_quality_snapshots_release_id"),
        "knowledge_quality_snapshots",
        ["release_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_quality_snapshots_scope_id"),
        "knowledge_quality_snapshots",
        ["scope_id"],
        unique=False,
    )
    op.create_index(
        "ix_quality_snapshot_scope",
        "knowledge_quality_snapshots",
        ["scope_type", "scope_id"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "knowledge_quality_gate_policies",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_quality_gate_policies_deleted_at"),
        "knowledge_quality_gate_policies",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_quality_gate_policies_org_id"),
        "knowledge_quality_gate_policies",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "uq_quality_gate_policy_org",
        "knowledge_quality_gate_policies",
        ["org_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "application_retrieval_policy_revisions",
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("application_id", sa.String(length=36), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("query_intelligence_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provider_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provider_weights", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("candidate_budget", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fanout_budget", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("latency_budget", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fallback_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("artifact_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fusion_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by_member_id", sa.String(length=36), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_application_retrieval_policy_revisions_application_id"),
        "application_retrieval_policy_revisions",
        ["application_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_application_retrieval_policy_revisions_deleted_at"),
        "application_retrieval_policy_revisions",
        ["deleted_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_application_retrieval_policy_revisions_org_id"),
        "application_retrieval_policy_revisions",
        ["org_id"],
        unique=False,
    )
    op.create_index(
        "uq_app_retrieval_policy_revision_version",
        "application_retrieval_policy_revisions",
        ["application_id", "revision_number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_app_retrieval_policy_single_active",
        "application_retrieval_policy_revisions",
        ["application_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL AND status = 'active'"),
    )

    op.add_column(
        "knowledge_evaluation_runs",
        sa.Column("release_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "knowledge_evaluation_runs",
        sa.Column("channel", sa.String(length=32), nullable=True),
    )
    op.create_index(
        op.f("ix_knowledge_evaluation_runs_release_id"),
        "knowledge_evaluation_runs",
        ["release_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_evaluation_runs_release_id"), table_name="knowledge_evaluation_runs")
    op.drop_column("knowledge_evaluation_runs", "channel")
    op.drop_column("knowledge_evaluation_runs", "release_id")

    op.drop_index(
        "uq_app_retrieval_policy_single_active",
        table_name="application_retrieval_policy_revisions",
    )
    op.drop_index(
        "uq_app_retrieval_policy_revision_version",
        table_name="application_retrieval_policy_revisions",
    )
    op.drop_index(
        op.f("ix_application_retrieval_policy_revisions_org_id"),
        table_name="application_retrieval_policy_revisions",
    )
    op.drop_index(
        op.f("ix_application_retrieval_policy_revisions_deleted_at"),
        table_name="application_retrieval_policy_revisions",
    )
    op.drop_index(
        op.f("ix_application_retrieval_policy_revisions_application_id"),
        table_name="application_retrieval_policy_revisions",
    )
    op.drop_table("application_retrieval_policy_revisions")

    op.drop_index("uq_quality_gate_policy_org", table_name="knowledge_quality_gate_policies")
    op.drop_index(
        op.f("ix_knowledge_quality_gate_policies_org_id"),
        table_name="knowledge_quality_gate_policies",
    )
    op.drop_index(
        op.f("ix_knowledge_quality_gate_policies_deleted_at"),
        table_name="knowledge_quality_gate_policies",
    )
    op.drop_table("knowledge_quality_gate_policies")

    op.drop_index("ix_quality_snapshot_scope", table_name="knowledge_quality_snapshots")
    op.drop_index(op.f("ix_knowledge_quality_snapshots_scope_id"), table_name="knowledge_quality_snapshots")
    op.drop_index(op.f("ix_knowledge_quality_snapshots_release_id"), table_name="knowledge_quality_snapshots")
    op.drop_index(op.f("ix_knowledge_quality_snapshots_org_id"), table_name="knowledge_quality_snapshots")
    op.drop_index(op.f("ix_knowledge_quality_snapshots_deleted_at"), table_name="knowledge_quality_snapshots")
    op.drop_table("knowledge_quality_snapshots")

    op.drop_index("uq_release_channel_app_name", table_name="knowledge_release_channels")
    op.drop_index(op.f("ix_knowledge_release_channels_org_id"), table_name="knowledge_release_channels")
    op.drop_index(op.f("ix_knowledge_release_channels_deleted_at"), table_name="knowledge_release_channels")
    op.drop_index(op.f("ix_knowledge_release_channels_application_id"), table_name="knowledge_release_channels")
    op.drop_table("knowledge_release_channels")

    op.drop_index("uq_application_release_version", table_name="knowledge_application_releases")
    op.drop_index(op.f("ix_knowledge_application_releases_org_id"), table_name="knowledge_application_releases")
    op.drop_index(op.f("ix_knowledge_application_releases_deleted_at"), table_name="knowledge_application_releases")
    op.drop_index(
        op.f("ix_knowledge_application_releases_application_id"),
        table_name="knowledge_application_releases",
    )
    op.drop_table("knowledge_application_releases")
