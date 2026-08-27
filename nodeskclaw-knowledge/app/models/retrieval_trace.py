"""RetrievalTrace ORM model for playground diagnostics."""

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# @lat: [[knowledge#Retrieval Playground And Trace]]
class RetrievalTrace(BaseModel):
    __tablename__ = "knowledge_retrieval_traces"

    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    knowledge_set_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    profile_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    profile_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    member_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    slice_results: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    timing: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    filter_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    chunk_traces: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    query_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_indexes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    effective_indexes: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    fallback_used: Mapped[bool | None] = mapped_column(nullable=True)
    fallback_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    execution_slices: Mapped[list | None] = mapped_column(JSONB, nullable=True)
