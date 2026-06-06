"""MessageEnvelope — CloudEvents-aligned message wrapper for the DeskClaw messaging system."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class SenderType(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    CRON = "cron"
    EXTERNAL = "external"


class IntentType(str, Enum):
    CHAT = "chat"
    COLLABORATE = "collaborate"
    NOTIFY = "notify"
    COMMAND = "command"
    ACK = "ack"


class Priority(str, Enum):
    CRITICAL = "critical"
    NORMAL = "normal"
    BACKGROUND = "background"


PRIORITY_WEIGHT = {
    Priority.CRITICAL: 8,
    Priority.NORMAL: 4,
    Priority.BACKGROUND: 1,
}


class DeliveryMode(str, Enum):
    SYNC = "sync"
    ASYNC = "async"
    SCHEDULED = "scheduled"


class Urgency(str, Enum):
    IMMEDIATE = "immediate"
    NORMAL = "normal"
    DEFERRED = "deferred"
    SCHEDULED = "scheduled"


@dataclass
class MessageSender:
    id: str
    type: SenderType
    name: str = ""
    instance_id: str | None = None


@dataclass
class MessageRouting:
    mode: str = "multicast"
    target: str = ""
    targets: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    max_hops: int = 5
    ttl: int = 0
    visited: list[str] = field(default_factory=list)
    priority: Priority | None = None


@dataclass
class MessageScheduling:
    delivery_mode: DeliveryMode = DeliveryMode.ASYNC
    urgency: Urgency = Urgency.NORMAL
    delay_seconds: int = 0
    deadline: str | None = None


@dataclass
class MessageData:
    sender: MessageSender
    intent: IntentType = IntentType.CHAT
    content: str = ""
    mentions: list[str] = field(default_factory=list)
    attachments: list[dict] = field(default_factory=list)
    file_references: list[dict] = field(default_factory=list)
    extensions: dict = field(default_factory=dict)
    routing: MessageRouting = field(default_factory=MessageRouting)
    scheduling: MessageScheduling = field(default_factory=MessageScheduling)
    priority: Priority = Priority.NORMAL


@dataclass
class MessageEnvelope:
    """CloudEvents-aligned message envelope with DeskClaw extensions."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: str = ""
    type: str = "deskclaw.msg.v1.chat"
    specversion: str = "1.0"
    time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    datacontenttype: str = "application/json"

    traceid: str = field(default_factory=lambda: str(uuid.uuid4()))
    spanid: str = field(default_factory=lambda: str(uuid.uuid4())[:16])
    workspaceid: str = ""
    causationid: str = ""
    correlationid: str = ""

    data: MessageData | None = None

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "source": self.source,
            "type": self.type,
            "specversion": self.specversion,
            "time": self.time,
            "datacontenttype": self.datacontenttype,
            "traceid": self.traceid,
            "spanid": self.spanid,
            "workspaceid": self.workspaceid,
            "causationid": self.causationid,
            "correlationid": self.correlationid,
        }
        if self.data:
            result["data"] = {
                "sender": {
                    "id": self.data.sender.id,
                    "type": self.data.sender.type.value,
                    "name": self.data.sender.name,
                    "instance_id": self.data.sender.instance_id,
                },
                "intent": self.data.intent.value,
                "content": self.data.content,
                "mentions": self.data.mentions,
                "attachments": self.data.attachments,
                "file_references": self.data.file_references,
                "extensions": self.data.extensions,
                "priority": self.data.priority.value,
                "routing": {
                    "mode": self.data.routing.mode,
                    "target": self.data.routing.target,
                    "targets": self.data.routing.targets,
                    "exclude": self.data.routing.exclude,
                    "max_hops": self.data.routing.max_hops,
                    "ttl": self.data.routing.ttl,
                    "visited": self.data.routing.visited,
                    "priority": self.data.routing.priority.value if self.data.routing.priority else None,
                },
                "scheduling": {
                    "delivery_mode": self.data.scheduling.delivery_mode.value,
                    "urgency": self.data.scheduling.urgency.value,
                    "delay_seconds": self.data.scheduling.delay_seconds,
                    "deadline": self.data.scheduling.deadline,
                },
            }
        return result

    @classmethod
    def from_dict(cls, d: dict) -> MessageEnvelope:
        data_dict = d.get("data")
        msg_data = None
        if data_dict:
            sender_d = data_dict.get("sender", {})
            msg_data = MessageData(
                sender=MessageSender(
                    id=sender_d.get("id", ""),
                    type=SenderType(sender_d.get("type", "user")),
                    name=sender_d.get("name", ""),
                    instance_id=sender_d.get("instance_id"),
                ),
                intent=IntentType(data_dict.get("intent", "chat")),
                content=data_dict.get("content", ""),
                mentions=data_dict.get("mentions", []),
                attachments=data_dict.get("attachments", []),
                file_references=data_dict.get("file_references", []),
                extensions=data_dict.get("extensions", {}),
                priority=Priority(data_dict.get("priority", "normal")),
            )
            routing_d = data_dict.get("routing", {})
            _rp = routing_d.get("priority")
            msg_data.routing = MessageRouting(
                mode=routing_d.get("mode", "multicast"),
                target=routing_d.get("target", ""),
                targets=routing_d.get("targets", []),
                exclude=routing_d.get("exclude", []),
                max_hops=routing_d.get("max_hops", 5),
                ttl=routing_d.get("ttl", 0),
                visited=routing_d.get("visited", []),
                priority=Priority(_rp) if _rp else None,
            )
            scheduling_d = data_dict.get("scheduling", {})
            msg_data.scheduling = MessageScheduling(
                delivery_mode=DeliveryMode(scheduling_d.get("delivery_mode", "async")),
                urgency=Urgency(scheduling_d.get("urgency", "normal")),
                delay_seconds=scheduling_d.get("delay_seconds", 0),
                deadline=scheduling_d.get("deadline"),
            )

        return cls(
            id=d.get("id", str(uuid.uuid4())),
            source=d.get("source", ""),
            type=d.get("type", "deskclaw.msg.v1.chat"),
            specversion=d.get("specversion", "1.0"),
            time=d.get("time", datetime.now(timezone.utc).isoformat()),
            datacontenttype=d.get("datacontenttype", "application/json"),
            traceid=d.get("traceid", str(uuid.uuid4())),
            spanid=d.get("spanid", ""),
            workspaceid=d.get("workspaceid", ""),
            causationid=d.get("causationid", ""),
            correlationid=d.get("correlationid", ""),
            data=msg_data,
        )
