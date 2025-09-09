# Quick Start

```python
import asyncio
from effectpy import *

async def main():
  base = Context()
  scope = Scope()
  env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(base, scope)

  compute = succeed(2).map(lambda x: x + 3).flat_map(lambda y: succeed(y * 2))
  run = instrument("compute.demo", compute, tags={"component": "docs"})
  v = await run._run(env)
  print("value:", v)

  await scope.close()

asyncio.run(main())
```

Next: read about [Effects](concepts/effects.md) and [Layers & Scope](concepts/layers_scope.md).

