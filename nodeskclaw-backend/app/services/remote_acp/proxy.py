from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

logger = logging.getLogger(__name__)


def _redact(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-2:]


async def proxy_text_frames(public_ws: WebSocket, agent_ws) -> None:
    async def client_to_agent() -> None:
        try:
            async for message in public_ws.iter_text():
                await agent_ws.send(message)
        except WebSocketDisconnect:
            return

    async def agent_to_client() -> None:
        async for message in agent_ws:
            text = message if isinstance(message, str) else message.decode("utf-8")
            await public_ws.send_text(text)

    tasks = [
        asyncio.create_task(client_to_agent()),
        asyncio.create_task(agent_to_client()),
    ]
    _done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    for task in pending:
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
