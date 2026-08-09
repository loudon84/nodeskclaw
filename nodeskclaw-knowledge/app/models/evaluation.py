"""Evaluation Set / Case / Run / Result ORM models."""

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class EvaluationSet(BaseModel):
    __tablename__ = "knowledge_evaluation_sets"

    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    knowledge_set_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)


class EvaluationCase(BaseModel):
    __tablename__ = "knowledge_evaluation_cases"

    evaluation_set_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    expected_source_file_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    expected_keywords: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    expected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)


class EvaluationRun(BaseModel):
    __tablename__ = "knowledge_evaluation_runs"

    evaluation_set_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    retrieval_profile_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    principal_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_by_member_id: Mapped[str] = mapped_column(String(36), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EvaluationResult(BaseModel):
    __tablename__ = "knowledge_evaluation_results"

    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    hit_at_k: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recall_at_k: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    mrr: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    returned_source_file_ids: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    unauthorized_hit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
