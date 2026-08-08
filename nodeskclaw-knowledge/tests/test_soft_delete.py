"""Soft-delete helpers."""

from app.models.base import BaseModel, not_deleted
from app.models.knowledge_base import KnowledgeBase


def test_not_deleted_predicate():
    clause = not_deleted(KnowledgeBase)
    assert clause is not None


def test_base_model_abstract():
    assert BaseModel.__abstract__ is True
