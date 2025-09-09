from __future__ import annotations
import asyncio
from typing import Generic, TypeVar, Optional

T = TypeVar("T")


class Deferred(Generic[T]):
    def __init__(self) -> None:
        self._f: asyncio.Future[T] = asyncio.get_event_loop().create_future()

    def done(self) -> bool:
        return self._f.done()

    async def await_(self) -> T:
        return await self._f

    def try_succeed(self, value: T) -> bool:
        if self._f.done():
            return False
        self._f.set_result(value)
        return True

    def succeed(self, value: T) -> None:
        if not self.try_succeed(value):
            raise RuntimeError("Deferred already completed")

    def try_fail(self, ex: BaseException) -> bool:
        if self._f.done():
            return False
        self._f.set_exception(ex)
        return True

    def fail(self, ex: BaseException) -> None:
        if not self.try_fail(ex):
            raise RuntimeError("Deferred already completed")

