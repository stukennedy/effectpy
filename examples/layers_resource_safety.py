"""
Layers + Scope: automatic resource acquisition/teardown with composition.

Run: python examples/layers_resource_safety.py
"""
import asyncio

from effectpy import (
    Context,
    Scope,
    Layer,
    from_resource,
    Effect,
    instrument,
    LoggerLayer,
)


class Connection:
    def __init__(self, name: str):
        self.name = name
        print(f"[conn] open {name}")

    async def query(self, x: int) -> int:
        await asyncio.sleep(0.01)
        return x * 3

    async def close(self) -> None:
        print(f"[conn] close {self.name}")


async def mk_primary(_):
    return Connection("primary")


async def close_conn(conn: Connection):
    await conn.close()


PrimaryLayer = from_resource(Connection, mk_primary, close_conn)


async def main():
    base = Context()
    scope = Scope()

    # Compose layers: logger in parallel with our resource (|)
    env = await (LoggerLayer | PrimaryLayer).build_scoped(base, scope)

    # Effect that uses the resource from the environment
    async def run_query(ctx: Context) -> int:
        conn = ctx.get(Connection)
        return await conn.query(7)

    eff = Effect(run_query)
    eff = instrument("layers.resource.query", eff, tags={"db": "primary"})

    val = await eff._run(env)
    print("query =>", val)  # 21

    # Scope ensures resources are closed in LIFO order
    await scope.close()


if __name__ == "__main__":
    asyncio.run(main())

