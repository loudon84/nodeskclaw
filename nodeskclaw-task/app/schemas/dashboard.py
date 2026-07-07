
from pydantic import Field

from app.schemas.common import CamelModel


class DashboardSummary(CamelModel):
    today_total: int = Field(serialization_alias="todayTotal")
    ready: int = 0
    running: int = 0
    waiting_human: int = Field(0, serialization_alias="waitingHuman")
    failed: int = 0
    success: int = 0
    success_rate: float = Field(0.0, serialization_alias="successRate")
    online_workers: int = Field(0, serialization_alias="onlineWorkers")
