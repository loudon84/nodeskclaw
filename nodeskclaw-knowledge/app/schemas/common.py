"""Common response schemas."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    error_code: int | None = None
    message_key: str | None = None
    message: str = "success"
    data: T | None = None


class PageData(BaseModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


class Pagination(BaseModel):
    page: int = 1
    page_size: int = 20
    total: int = 0


class PaginatedResponse(BaseModel, Generic[T]):
    code: int = 0
    error_code: int | None = None
    message_key: str | None = None
    message: str = "success"
    data: PageData[T] = Field(default_factory=PageData)
