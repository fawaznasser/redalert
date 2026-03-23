from __future__ import annotations

import asyncio
import json
import threading
from typing import Any


class LiveUpdateBroker:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._lock = threading.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue()
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    async def publish(self, payload: dict[str, Any]) -> None:
        message = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            await subscriber.put(message)

    def publish_from_thread(self, payload: dict[str, Any]) -> None:
        if self._loop is None:
            return
        if self._loop.is_closed():
            return
        try:
            asyncio.run_coroutine_threadsafe(self.publish(payload), self._loop)
        except RuntimeError:
            return


live_updates = LiveUpdateBroker()
