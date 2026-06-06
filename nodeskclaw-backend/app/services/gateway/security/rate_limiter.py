import time
from collections import deque
from threading import Lock


class RateLimiter:
    def __init__(self) -> None:
        self._global_lock = Lock()
        self._global_counter: deque = deque()
        self._key_counters: dict[str, deque] = {}
        self._key_lock = Lock()

    def check_global(self, rpm: int | None) -> bool:
        if rpm is None or rpm <= 0:
            return True
        now = time.time()
        window = 60.0
        with self._global_lock:
            while self._global_counter and self._global_counter[0] < now - window:
                self._global_counter.popleft()
            if len(self._global_counter) >= rpm:
                return False
            self._global_counter.append(now)
            return True

    def check_per_key(self, key: str, rpm: int | None) -> bool:
        if rpm is None or rpm <= 0:
            return True
        if not key:
            return True
        now = time.time()
        window = 60.0
        with self._key_lock:
            if key not in self._key_counters:
                self._key_counters[key] = deque()
            counter = self._key_counters[key]
            while counter and counter[0] < now - window:
                counter.popleft()
            if len(counter) >= rpm:
                return False
            counter.append(now)
            return True
