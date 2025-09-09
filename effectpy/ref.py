from __future__ import annotations
import asyncio
from typing import Callable, Generic, Tuple, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class Ref(Generic[T]):
    def __init__(self, initial: T):
        self._value: T = initial
        self._lock = asyncio.Lock()

    async def get(self) -> T:
        async with self._lock:
            return self._value

    async def set(self, v: T) -> None:
        async with self._lock:
            self._value = v

    async def update(self, f: Callable[[T], T]) -> T:
        async with self._lock:
            self._value = f(self._value)
            return self._value

    async def modify(self, f: Callable[[T], Tuple[R, T]]) -> R:
        async with self._lock:
            out, new_v = f(self._value)
            self._value = new_v
            return out

