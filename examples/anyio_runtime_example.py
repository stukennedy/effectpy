"""
AnyIO Runtime example (optional): run with Trio/AnyIO semantics.

This example requires `anyio` to be installed. If not available, it prints
an informative message and exits gracefully.

Run: python examples/anyio_runtime_example.py
"""
import asyncio

try:
    import anyio  # noqa: F401
    HAVE_ANYIO = True
except Exception:
    HAVE_ANYIO = False

from effectpy import (
    Effect,
    Context,
    Scope,
    instrument,
    LoggerLayer,
    MetricsLayer,
    TracerLayer,
)

if HAVE_ANYIO:
    # Import directly from the module to avoid relying on optional re-export
    from effectpy.anyio_runtime import AnyIORuntime


async def inc(_):
    await asyncio.sleep(0.02)
    return 1


async def mul(_):
    await asyncio.sleep(0.03)
    return 2


async def main_asyncio():
    if not HAVE_ANYIO:
        print("anyio is not installed; skipping AnyIO example.")
        return

    base = Context()
    scope = Scope()
    env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(base, scope)

    eff1 = instrument("anyio.inc", Effect(inc), tags={"rt": "anyio"})
    eff2 = instrument("anyio.mul", Effect(mul), tags={"rt": "anyio"})

    async with AnyIORuntime(env) as rt:
        f1 = await rt.fork(eff1)  # type: ignore[arg-type]
        f2 = await rt.fork(eff2)  # type: ignore[arg-type]
        e1, e2 = await asyncio.gather(f1.await_(), f2.await_())
        print("AnyIO exits =>", e1.value, e2.value)

    await scope.close()


if __name__ == "__main__":
    asyncio.run(main_asyncio())
