from __future__ import annotations
import asyncio
from typing import Callable, Generic, TypeVar, Awaitable
from .channel import Channel
from .core import Effect
from .context import Context
from .stream import StreamE
from .queue import Queue, QueueClosed

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
        async def run(ctx: Context):
            # Build a StreamE from the source Channel
            s = StreamE.from_channel(self.source)
            # Adapt each Stage to via_effect
            for st in self.stages:
                def make_eff(st_local: Stage):
                    def eff(x):
                        async def run_effect(_: Context):
                            return await st_local.func(x)
                        return Effect(run_effect)
                    return eff
                s = s.via_effect(make_eff(st), workers=max(1, st.workers), out_capacity=max(0, st.out_capacity))  # type: ignore

            # Start the stream in the background and pump to the provided Channel
            out_q: Queue[B] = Queue()
            err_q: Queue[BaseException] = Queue()
            asyncio.create_task(s._build(out_q, err_q)._run(ctx))

            async def pump():
                while True:
                    try:
                        v = await out_q.receive()
                    except QueueClosed:
                        return
                    await out.send(v)

            asyncio.create_task(pump())
            # Return immediately, leaving background tasks running
            await asyncio.sleep(0)
            return None
        return Effect(run)

def stage(func: Callable[[A], Awaitable[B]], workers: int = 1, out_capacity: int = 0) -> Stage[A,B]:
    return Stage(func, workers, out_capacity)
