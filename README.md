

![EffectPy Architecture](img/effectpy_arch.png)

# effectpy

Effect/ZIO-inspired structured async for Python.

## Why effectpy?

`asyncio` is powerful but messy: exceptions leak, cancellations are tricky, resources are forgotten, and observability is bolted on later.  
**effectpy** brings the semantics of [Effect TS](https://effect.website) / [ZIO](https://zio.dev) into Python, giving you:

- **Structured async without spaghetti**
  - Every async operation is an `Effect` you can compose, transform, retry, race, zip, and run in parallel.

- **Automatic resource safety**
  - `Layer` + `Scope` ensure resources are acquired and released correctly, in order.

- **Structured errors, not random exceptions**
  - Failures are rich `Cause` trees: fail, die, interrupt, both, then — with annotations and stack traces.

- **Deterministic concurrency**
  - Built-ins for `race`, `zip_par`, `for_each_par`, cancellation masks, `FiberRef` locals.
  - Works with both `asyncio` and `anyio` (Trio).

- **Observability baked in**
  - `instrument("name", tags={...})` logs, records metrics, and traces.
  - Export spans/metrics to OTLP/Prometheus/OpenTelemetry.

- **Composable streaming and pipelines**
  - `StreamE` with error channel.
  - Channels + Pipelines with backpressure.

- **Test-friendly clocks and supervision**
  - `TestClock` for deterministic time in tests.
  - Supervisors restart effects with retry schedules.

## Example: Scoped DB pipeline

```python
import asyncio
from effectpy import *

class DB:
    async def query(self, x: int) -> int:
        await asyncio.sleep(0.01)
        return x * 2

DBLayer = from_resource(DB, lambda _: DB(), lambda _: asyncio.sleep(0))

async def main():
    base = Context()
    scope = Scope()
    env = await (LoggerLayer | MetricsLayer | TracerLayer | DBLayer).build_scoped(base, scope)

    db = env.get(DB)
    src, out = Channel[int](2), Channel[int](2)

    async def producer():
        for i in range(5):
            await src.send(i)

    async def stage1(x: int) -> int: return (x + 1)
    async def stage2(x: int) -> int: return await db.query(x)

    pipe = Pipeline[int,int](src) \        .via(stage(stage1, workers=2)) \        .via(stage(stage2, workers=2)) \        .to_channel(out)

    async def consumer():
        for _ in range(5):
            print("OUT:", await out.receive())

    run = instrument("pipeline.run", pipe, tags={"component":"db","env":"dev"})
    await asyncio.gather(producer(), run._run(env), consumer())

    await scope.close()

asyncio.run(main())
```

Output:

```
OUT: 2
OUT: 4
OUT: 6
OUT: 8
OUT: 10
```

---

effectpy = **`asyncio` with guardrails and batteries**:
- Guardrails: structured errors, cancellation, resource safety
- Batteries: observability, retries, pipelines, test clocks, supervision
