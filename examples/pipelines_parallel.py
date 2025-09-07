"""
Pipelines + Channels: parallel stages with backpressure and observability.

Run: python examples/pipelines_parallel.py
"""
import asyncio

from effectpy import (
    Context,
    Scope,
    Channel,
    Pipeline,
    stage,
    instrument,
    LoggerLayer,
    MetricsLayer,
    TracerLayer,
)


async def main():
    base = Context()
    scope = Scope()
    env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(base, scope)

    src: Channel[int] = Channel(maxsize=2)
    out: Channel[int] = Channel(maxsize=2)

    async def producer(n: int):
        for i in range(n):
            await src.send(i)

    async def inc(x: int) -> int:
        await asyncio.sleep(0.005)
        return x + 1

    async def square(x: int) -> int:
        await asyncio.sleep(0.005)
        return x * x

    # Build a pipeline with two parallelized stages
    pipe = (
        Pipeline[int, int](src)
        .via(stage(inc, workers=2, out_capacity=4))
        .via(stage(square, workers=2, out_capacity=4))
        .to_channel(out)
    )

    run_effect = instrument(
        "pipeline.compute",
        pipe,
        tags={"component": "pipeline", "env": "demo"},
    )

    N = 8
    async def consumer(n: int):
        for _ in range(n):
            v = await out.receive()
            print("OUT:", v)

    await asyncio.gather(producer(N), run_effect._run(env), consumer(N))
    await scope.close()


if __name__ == "__main__":
    asyncio.run(main())

