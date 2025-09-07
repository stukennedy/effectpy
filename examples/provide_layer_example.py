"""
Using Effect.provide to scope layers just for one effect.

Run: python examples/provide_layer_example.py
"""
import asyncio

from effectpy import (
    Effect,
    Context,
    LoggerLayer,
    ConsoleLogger,
)


async def say_hello(ctx: Context) -> str:
    # Pull logger from context provided to this effect only
    logger = ctx.get(ConsoleLogger)
    await logger.info("hello via provide()")
    return "hello"


async def main():
    eff = Effect(say_hello)
    # No global env; provide the logger layer just for this run
    res = await eff.provide(LoggerLayer)._run(Context())
    print("result:", res)


if __name__ == "__main__":
    asyncio.run(main())

