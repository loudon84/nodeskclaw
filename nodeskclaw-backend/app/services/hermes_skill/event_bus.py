import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class EventBus:
    _instance = None

    def __init__(self):
        self._waiters: dict[str, list[asyncio.Event]] = defaultdict(list)

    @classmethod
    def get_instance(cls) -> "EventBus":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def notify(self, task_id: str, event_data: dict | None = None):
        waiters = self._waiters.get(task_id, [])
        for waiter in waiters:
            if not waiter.is_set():
                waiter.set()

    async def wait(self, task_id: str, timeout: float = 5.0) -> bool:
        event = asyncio.Event()
        self._waiters[task_id].append(event)
        try:
            return await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return False
        finally:
            waiters = self._waiters.get(task_id, [])
            if event in waiters:
                waiters.remove(event)

    def clear(self, task_id: str):
        self._waiters.pop(task_id, None)
