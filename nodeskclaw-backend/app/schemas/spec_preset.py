"""Instance spec preset schemas."""

from pydantic import BaseModel, field_validator


class SpecPresetInput(BaseModel):
    key: str
    label: str
    desc: str = ""
    cpu: float
    memory: float
    storage: int = 20

    @field_validator("cpu")
    @classmethod
    def cpu_min(cls, v: float) -> float:
        if v < 0.25:
            raise ValueError("CPU 最小为 0.25 核")
        return v

    @field_validator("memory")
    @classmethod
    def memory_min(cls, v: float) -> float:
        if v < 0.5:
            raise ValueError("内存最小为 0.5 GB")
        return v

    @field_validator("storage")
    @classmethod
    def storage_min(cls, v: int) -> int:
        if v < 20:
            raise ValueError("存储最小为 20 Gi")
        return v


class SpecPresetOutput(SpecPresetInput):
    cpu_request: str
    cpu_limit: str
    mem_request: str
    mem_limit: str
    quota_cpu: str
    quota_mem: str


def _fmt_mem(gb: float) -> str:
    """Format memory value: use Gi when possible, otherwise Mi."""
    if gb >= 1 and gb == int(gb):
        return f"{int(gb)}Gi"
    return f"{int(gb * 1024)}Mi"


def derive_preset(p: SpecPresetInput) -> SpecPresetOutput:
    cpu_lim_m = int(p.cpu * 1000)
    cpu_req_m = int(p.cpu * 500)
    mem_half = p.memory / 2
    return SpecPresetOutput(
        **p.model_dump(),
        cpu_limit=f"{cpu_lim_m}m",
        cpu_request=f"{cpu_req_m}m",
        mem_limit=_fmt_mem(p.memory),
        mem_request=_fmt_mem(mem_half),
        quota_cpu=str(p.cpu) if p.cpu != int(p.cpu) else str(int(p.cpu)),
        quota_mem=_fmt_mem(p.memory),
    )


DEFAULT_SPEC_PRESETS: list[dict] = [
    {"key": "small", "label": "轻量", "desc": "写周报、查资料、日常问答", "cpu": 2, "memory": 4, "storage": 20},
    {"key": "medium", "label": "标准", "desc": "代码审查、文档生成、会议纪要", "cpu": 4, "memory": 8, "storage": 40},
    {"key": "large", "label": "高性能", "desc": "浏览器自动化、代码开发、数据分析", "cpu": 8, "memory": 16, "storage": 80},
]
