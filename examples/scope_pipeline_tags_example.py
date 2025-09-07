import asyncio
from effectpy import (
    Context, from_resource, Layer, Scope,
    Pipeline, stage, Channel, instrument,
    ConsoleLogger, LoggerLayer, MetricsLayer, TracerLayer, Effect
)

class DB:
    async def query(self, x: int) -> int:
        await asyncio.sleep(0.01)
        return x * 2

async def mk_db(_): return DB()
async def close_db(_): return None
DBLayer = from_resource(DB, mk_db, close_db)

async def main():
    base = Context()
    scope = Scope()
    env = await (LoggerLayer | MetricsLayer | TracerLayer | DBLayer).build_scoped(base, scope)

    db = env.get(DB)
    src = Channel[int](maxsize=2)
    out = Channel[int](maxsize=2)

    async def producer():
        for i in range(5):
            await src.send(i)

    async def query_stage(x: int) -> int:
        return await db.query(x)

    pipe = Pipeline[int,int](src).via(stage(query_stage, workers=2, out_capacity=2)).to_channel(out)

    async def consumer():
        for _ in range(5):
            v = await out.receive()
            print("OUT:", v)

    run_effect = instrument("pipeline.run", pipe, tags={"component":"db","env":"dev"})

    await asyncio.gather(producer(), run_effect._run(env), consumer())

    await scope.close()

if __name__ == "__main__":
    asyncio.run(main())
