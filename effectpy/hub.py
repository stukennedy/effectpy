from __future__ import annotations
import asyncio
from typing import Generic, Set, TypeVar

from .queue import Queue, QueueClosed

T = TypeVar("T")


class HubClosed(Exception):
    pass


class Subscription(Generic[T]):
    def __init__(self, hub: "Hub[T]", q: Queue[T]):
        self._hub = hub
        self._q = q
        self._closed = False

    async def receive(self) -> T:
        return await self._q.receive()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._hub._unsubscribe(self._q)

    def size(self) -> int:
        return self._q.size()


class Hub(Generic[T]):
    def __init__(self):
        self._subs: Set[Queue[T]] = set()
        self._closed = False
        self._lock = asyncio.Lock()

    async def subscribe(self, maxsize: int = 0) -> Subscription[T]:
        async with self._lock:
            if self._closed:
                raise HubClosed("subscribe on closed hub")
            q: Queue[T] = Queue(maxsize=maxsize)
            self._subs.add(q)
            return Subscription(self, q)

    async def _unsubscribe(self, q: Queue[T]) -> None:
        async with self._lock:
            if q in self._subs:
                self._subs.remove(q)
            await q.close()

    async def publish(self, item: T) -> None:
        async with self._lock:
            if self._closed:
                raise HubClosed("publish on closed hub")
            subs = list(self._subs)
        # push outside the lock to avoid deadlocks/backpressure holding the lock
        for q in subs:
            await q.send(item)

    async def close(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            subs = list(self._subs)
            self._subs.clear()
        # Close all subscriber queues
        for q in subs:
            await q.close()

