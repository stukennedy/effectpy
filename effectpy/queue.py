from __future__ import annotations
import asyncio
from collections import deque
from typing import Deque, Generic, Optional, TypeVar

T = TypeVar("T")


class QueueClosed(Exception):
    pass


class Queue(Generic[T]):
    def __init__(self, maxsize: int = 0):
        self._maxsize = max(0, int(maxsize))
        self._buf: Deque[T] = deque()
        self._closed = False
        self._cond = asyncio.Condition()

    def size(self) -> int:
        return len(self._buf)

    def closed(self) -> bool:
        return self._closed

    async def close(self) -> None:
        async with self._cond:
            self._closed = True
            self._cond.notify_all()

    async def send(self, item: T) -> None:
        async with self._cond:
            if self._closed:
                raise QueueClosed("send on closed queue")
            while self._maxsize > 0 and len(self._buf) >= self._maxsize:
                await self._cond.wait()
            self._buf.append(item)
            self._cond.notify_all()

    async def receive(self) -> T:
        async with self._cond:
            while True:
                if self._buf:
                    v = self._buf.popleft()
                    self._cond.notify_all()
                    return v
                if self._closed:
                    raise QueueClosed("receive on closed and drained queue")
                await self._cond.wait()

