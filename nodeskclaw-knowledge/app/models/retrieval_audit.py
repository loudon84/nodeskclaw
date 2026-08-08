"""RetrievalAudit ORM model."""

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class RetrievalAudit(BaseModel):
    __tablename__ = "retrieval_audits"

    member_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    knowledge_set_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filtered_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    returned_chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source_file_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ok")
    plan_kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ragflow_call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="direct_retrieval", index=True)
    execution_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    successful_slice_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_slice_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
