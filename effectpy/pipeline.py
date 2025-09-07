from __future__ import annotations
import asyncio
from typing import Callable, Generic, TypeVar, Awaitable
from .channel import Channel
from .core import Effect
from .context import Context

A = TypeVar('A'); B = TypeVar('B')

class Stage(Generic[A,B]):
    def __init__(self, func: Callable[[A], Awaitable[B]], workers: int = 1, out_capacity: int = 0):
        self.func = func; self.workers = workers; self.out_capacity = out_capacity

class Pipeline(Generic[A,B]):
    def __init__(self, source: Channel[A]): self.source = source; self.stages: list[Stage] = []
    def via(self, stage: Stage[A,B]) -> 'Pipeline[B,B]':
        self.stages.append(stage)  # type: ignore
        return self  # type: ignore

    def to_channel(self, out: Channel[B]) -> Effect[object, Exception, None]:
        async def run(_: Context):
            prev = self.source
            # Build each stage, capturing loop variables properly
            for st in self.stages:
                nxt: Channel[B] = Channel[B](maxsize=st.out_capacity)  # type: ignore

                async def worker(prev_=prev, st_=st, nxt_=nxt):  # capture by default args
                    while True:
                        item = await prev_.receive()
                        res = await st_.func(item)  # type: ignore
                        await nxt_.send(res)

                for _ in range(max(1, st.workers)):
                    asyncio.create_task(worker())
                prev = nxt  # type: ignore

            async def pump(prev_=prev):
                while True:
                    v = await prev_.receive()
                    await out.send(v)
            asyncio.create_task(pump())
            await asyncio.sleep(0)
            return None
        return Effect(run)

def stage(func: Callable[[A], Awaitable[B]], workers: int = 1, out_capacity: int = 0) -> Stage[A,B]:
    return Stage(func, workers, out_capacity)
