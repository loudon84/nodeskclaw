from typing import Any

from pydantic import BaseModel, Field


class ExpertHealthRuntimeItem(BaseModel):
    expert_slug: str
    display_name: str
    status: str
    agent_alias: str | None = None
    api_server: str | None = None
    agent_callable: bool = False
    runtime_ready: bool = False


class ExpertHealthResponse(BaseModel):
    ok: bool
    status: str
    gateway: dict[str, str]
    catalog: dict[str, int]
    runtimes: list[ExpertHealthRuntimeItem] = Field(default_factory=list)
