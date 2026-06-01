"""Agent ingestion — converts Channel Plugin SSE events into MessageEnvelopes."""

from __future__ import annotations

from app.services.runtime.messaging.envelope import (
    IntentType,
    MessageData,
    MessageEnvelope,
    MessageRouting,
    MessageSender,
    Priority,
    SenderType,
)


def build_agent_collaboration_envelope(
    *,
    workspace_id: str,
    source_instance_id: str,
    source_name: str,
    target: str,
    content: str,
    depth: int = 0,
    conversation_id: str | None = None,
    group_member_ids: list[str] | None = None,
) -> MessageEnvelope:
    mention_targets: list[str] = []
    if target and target != "broadcast":
        parts = target.split(":", 1)
        if len(parts) == 2:
            mention_targets = [parts[1]]

    if group_member_ids and len(group_member_ids) > 0:
        targets = [mid for mid in group_member_ids if mid != source_instance_id]
        mode = "multicast" if len(targets) > 1 else "unicast"
    elif mention_targets:
        targets = mention_targets
        mode = "unicast"
    else:
        targets = []
        mode = "broadcast"

    extensions: dict = {"depth": depth, "mention_targets": mention_targets}
    if conversation_id:
        extensions["conversation_id"] = conversation_id

    return MessageEnvelope(
        source=f"agent/{source_instance_id}",
        type="deskclaw.msg.v1.collaborate",
        workspaceid=workspace_id,
        data=MessageData(
            sender=MessageSender(
                id=source_instance_id,
                type=SenderType.AGENT,
                name=source_name,
                instance_id=source_instance_id,
            ),
            intent=IntentType.COLLABORATE,
            content=content,
            mentions=mention_targets,
            priority=Priority.CRITICAL,
            extensions=extensions,
            routing=MessageRouting(mode=mode, targets=targets, max_hops=5),
        ),
    )
