"""
Fibers with Runtime: run effects concurrently and observe exits.

Run: python examples/fibers_concurrency.py
"""
import asyncio

from effectpy import (
    Effect,
    Context,
    Scope,
    Runtime,
    instrument,
    LoggerLayer,
    MetricsLayer,
    TracerLayer,
)


async def slow_inc(_):
    await asyncio.sleep(0.05)
    return 1


async def slow_double(_):
    await asyncio.sleep(0.07)
    return 2


async def long_running(_):
    # Simulate a long task; we'll cancel it via fiber.interrupt()
    try:
        await asyncio.sleep(10)
    except asyncio.CancelledError:
        # Cleanup or compensations would go here
        raise


async def main():
    base = Context()
    scope = Scope()
    env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(base, scope)

    # Create a runtime bound to our environment
    rt = Runtime(env)

    # Instrumented effects
    inc = instrument("inc", Effect(slow_inc), tags={"worker": "A"})
    dbl = instrument("dbl", Effect(slow_double), tags={"worker": "B"})
    long = instrument("long", Effect(long_running), tags={"worker": "C"})

    # Fork two computations and await both
    f1 = rt.fork(inc)
    f2 = rt.fork(dbl)
    e1, e2 = await asyncio.gather(f1.await_(), f2.await_())
    print("fork results =>", e1.value, e2.value)

    # Start a long-running fiber and interrupt it
    f3 = rt.fork(long)
    await asyncio.sleep(0.02)
    f3.interrupt()
    e3 = await f3.await_()
    print("long fiber exit =>", e3.cause.kind)

    await scope.close()


if __name__ == "__main__":
    asyncio.run(main())

