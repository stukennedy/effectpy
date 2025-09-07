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
            for st in self.stages:
                nxt: Channel[B] = Channel[B](maxsize=st.out_capacity)  # type: ignore
                async def worker():
                    while True:
                        item = await prev.receive()
                        res = await st.func(item)  # type: ignore
                        await nxt.send(res)
                tasks = [asyncio.create_task(worker()) for _ in range(max(1, st.workers))]
                prev = nxt  # type: ignore
            async def pump():
                while True:
                    v = await prev.receive()
                    await out.send(v)
            asyncio.create_task(pump())
            await asyncio.sleep(0)
            return None
        return Effect(run)

def stage(func: Callable[[A], Awaitable[B]], workers: int = 1, out_capacity: int = 0) -> Stage[A,B]:
    return Stage(func, workers, out_capacity)
