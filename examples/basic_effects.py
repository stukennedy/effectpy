"""
Basic effects: composition, error handling, and instrumentation.

Run: python examples/basic_effects.py
"""
import asyncio

from effectpy import (
    Effect,
    succeed,
    fail,
    attempt,
    instrument,
    Context,
    Scope,
    LoggerLayer,
    MetricsLayer,
    TracerLayer,
)


async def main():
    # Build an environment with logger+metrics+tracer, scoped for resource safety
    base = Context()
    scope = Scope()
    env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(base, scope)

    # Compose effects: map/flat_map
    compute = succeed(2).map(lambda x: x + 3).flat_map(lambda y: succeed(y * 2))

    # Handle errors using Failure channel
    def bad_sync():
        raise ValueError("boom")

    recover = (
        attempt(bad_sync, lambda ex: f"bad:{type(ex).__name__}")
        .catch_all(lambda e: succeed(f"recovered:{e}"))
    )

    # Add observability via instrumentation with tags
    tagged_compute = instrument(
        "compute.ok",
        compute,
        tags={"component": "demo", "stage": "ok"},
    )
    tagged_recover = instrument(
        "compute.recover",
        recover,
        tags={"component": "demo", "stage": "recover"},
    )

    # Run both and show results
    v1 = await tagged_compute._run(env)
    v2 = await tagged_recover._run(env)
    print("compute.ok =>", v1)          # 10
    print("compute.recover =>", v2)     # recovered:bad:ValueError

    await scope.close()


if __name__ == "__main__":
    asyncio.run(main())

