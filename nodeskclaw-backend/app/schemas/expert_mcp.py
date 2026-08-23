from typing import Any

from pydantic import BaseModel, Field

from app.contracts.work_expert.constants import (
    WORK_EXPERT_CAPABILITIES,
    WORK_EXPERT_CONTRACT_NAME,
    WORK_EXPERT_CONTRACT_VERSION,
)


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
    contractName: str = WORK_EXPERT_CONTRACT_NAME
    contractVersion: str = WORK_EXPERT_CONTRACT_VERSION
    capabilities: dict[str, Any] = Field(default_factory=lambda: dict(WORK_EXPERT_CAPABILITIES))
    gateway: dict[str, str]
    catalog: dict[str, int]
    runtimes: list[ExpertHealthRuntimeItem] = Field(default_factory=list)
