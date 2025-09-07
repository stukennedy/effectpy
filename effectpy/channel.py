from __future__ import annotations
import asyncio
from typing import Generic, TypeVar, Callable, Awaitable, Optional, Iterable, AsyncIterator
from .core import Effect
from .context import Context
A = TypeVar('A'); B = TypeVar('B'); R = TypeVar('R'); E = TypeVar('E')

class Channel(Generic[A]):
    def __init__(self, maxsize: int = 0):
        self._q: asyncio.Queue[A] = asyncio.Queue(maxsize=maxsize); self._closed=False
    async def send(self, a: A) -> None:
        if self._closed: raise RuntimeError("send on closed channel")
        await self._q.put(a)
    async def close(self)->None: self._closed=True
    async def receive(self) -> A: return await self._q.get()
    def size(self)->int: return self._q.qsize()
