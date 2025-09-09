from __future__ import annotations
import asyncio
import time
from typing import Optional

from .layer import from_resource, Layer
from .context import Context


class Clock:
    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(max(0.0, seconds))

    def now(self) -> float:
        return time.monotonic()


class TestClock(Clock):
    def __init__(self, start: float = 0.0) -> None:
        self._now = float(start)

    async def sleep(self, seconds: float) -> None:  # type: ignore[override]
        self._now += max(0.0, seconds)
        # Yield to loop to allow awaiting code to proceed without delay
        await asyncio.sleep(0)

    def now(self) -> float:  # type: ignore[override]
        return self._now


async def _mk_clock(_ctx: Context) -> Clock:
    return Clock()


async def _close_clock(_c: Clock) -> None:
    return None


ClockLayer = from_resource(Clock, _mk_clock, _close_clock)


def TestClockLayer(start: float = 0.0) -> Layer:
    async def mk(_ctx: Context) -> Clock:
        return TestClock(start)

    async def close(_c: Clock) -> None:
        return None

    # Register under base Clock type for consumer transparency
    return from_resource(Clock, mk, close)


# Effect helpers
from .core import Effect


def sleep(seconds: float) -> Effect[object, object, None]:
    async def run(ctx: Context) -> None:
        clk = ctx.get(Clock)
        await clk.sleep(seconds)
        return None

    return Effect(run)


def current_time() -> Effect[object, object, float]:
    async def run(ctx: Context) -> float:
        clk = ctx.get(Clock)
        return clk.now()

    return Effect(run)

