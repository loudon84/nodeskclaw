from datetime import datetime, timezone
from types import SimpleNamespace

from app.models.hermes_skill.hermes_task import EventType
from app.services.hermes_skill.task_event_stream_formatter import build_sse_data


def _event(event_type: EventType, payload: dict | None = None, seq: int = 1):
    return SimpleNamespace(
        event_type=event_type,
        event_seq=seq,
        payload=payload or {},
        created_at=datetime.now(timezone.utc),
    )


def test_build_sse_data_progress_includes_expert_metadata():
    event = _event(
        EventType.HERMES_RUN_DELTA,
        {
            "mcp_event": "task.progress",
            "stage": "customer_research",
            "message": "正在分析客户画像...",
            "progress": 0.45,
            "expert": {
                "kind": "expert",
                "slug": "call-prep",
                "display_name": "客户研究员",
            },
            "team": {
                "slug": "sales-tianji",
                "display_name": "销售准备团队",
            },
            "agent": {
                "agent_profile": "writer",
                "hermes_agent_instance_id": "agent-1",
            },
        },
    )
    data = build_sse_data(event, "task-1")
    assert data["event"] == "task.progress"
    assert data["expert"]["slug"] == "call-prep"
    assert data["team"]["slug"] == "sales-tianji"
    assert data["agent"]["agent_profile"] == "writer"


def test_build_sse_data_team_member_event_name():
    event = _event(
        EventType.HERMES_RUN_DELTA,
        {
            "mcp_event": "team.member.progress",
            "stage": "research",
            "message": "member working",
        },
    )
    data = build_sse_data(event, "task-1")
    assert data["event"] == "team.member.progress"
