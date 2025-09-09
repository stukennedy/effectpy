---
title: effectpy
description: Effect-inspired structured async for Python with guaranteed resource safety, rich error handling, and built-in observability
---

<div class="hero-section" style="text-align: center; margin-bottom: 3rem;">
  <img src="https://raw.githubusercontent.com/stukennedy/effectpy/main/img/effectpy.png" alt="effectpy logo" width="200" style="margin-bottom: 1rem;" />
  
  <h1 style="font-size: 3rem; margin-bottom: 1rem; background: linear-gradient(45deg, #3f51b5, #9c27b0); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">effectpy</h1>
  
  <p style="font-size: 1.3rem; color: #666; margin-bottom: 2rem;">Effect-inspired structured async for Python</p>
  
  <div style="display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap;">
    <a href="installation/" class="md-button md-button--primary">Get Started</a>
    <a href="quickstart/" class="md-button">Quick Start</a>
    <a href="https://github.com/stukennedy/effectpy" class="md-button">View on GitHub</a>
  </div>
</div>

## Why effectpy?

`asyncio` is powerful but messy: exceptions leak, cancellations are tricky, resources are forgotten, and observability is bolted on later. **effectpy** brings the battle-tested semantics of [Effect TS](https://effect.website) and [ZIO](https://zio.dev) to Python.

<div class="grid cards" markdown>

-   :material-shield-check:{ .lg .middle } **Guaranteed Resource Safety**

    ---

    Every resource is automatically cleaned up in the correct order, even when errors occur or operations are cancelled.

    [:octicons-arrow-right-24: Learn about Layers & Scope](concepts/layers_scope.md)

-   :material-lightning-bolt:{ .lg .middle } **Structured Concurrency**

    ---

    Race, zip, and parallelize operations with deterministic cancellation. No more leaked tasks or zombie coroutines.

    [:octicons-arrow-right-24: Explore concurrency patterns](guides/concurrency.md)

-   :material-bug:{ .lg .middle } **Rich Error Handling**

    ---

    Failures are first-class citizens with structured `Cause` trees, annotations, and stack traces. No more mysterious exceptions.

    [:octicons-arrow-right-24: Understanding Effects](concepts/effects.md)

-   :material-eye:{ .lg .middle } **Built-in Observability**

    ---

    Automatic logging, metrics, and tracing with OpenTelemetry integration. Understand your async code's behavior.

    [:octicons-arrow-right-24: Observability guide](concepts/observability.md)

-   :material-pipe:{ .lg .middle } **Streaming & Pipelines**

    ---

    Process data streams with backpressure, error channels, and parallel stages. Built for real-world data processing.

    [:octicons-arrow-right-24: Streams & Channels](concepts/streams_channels.md)

-   :material-test-tube:{ .lg .middle } **Test-Friendly**

    ---

    Deterministic test clocks, controllable time, and supervision make testing async code predictable.

    [:octicons-arrow-right-24: Testing patterns](guides/concurrency.md#testing-with-testclock)

</div>

## Quick Example

```python title="Scoped DB Pipeline with Observability"
import asyncio
from effectpy import *

class DB:
    async def query(self, x: int) -> int:
        await asyncio.sleep(0.01)  # Simulate DB call
        return x * 2

# Resource layer with automatic cleanup
DBLayer = from_resource(DB, lambda _: DB(), lambda _: asyncio.sleep(0))

async def main():
    base = Context()
    scope = Scope()
    
    # Compose observability + DB layers
    env = await (LoggerLayer | MetricsLayer | TracerLayer | DBLayer).build_scoped(base, scope)
    
    db = env.get(DB)
    src, out = Channel[int](2), Channel[int](2)
    
    # Parallel pipeline stages
    pipe = Pipeline[int,int](src) \
        .via(stage(lambda x: x + 1, workers=2)) \
        .via(stage(lambda x: db.query(x), workers=2)) \
        .to_channel(out)
    
    async def producer():
        for i in range(5):
            await src.send(i)
    
    async def consumer():
        for _ in range(5):
            print(f"Result: {await out.receive()}")
    
    # Instrument the pipeline
    instrumented = instrument("pipeline.run", pipe, tags={"env": "demo"})
    
    # Run everything concurrently
    await asyncio.gather(
        producer(), 
        instrumented._run(env), 
        consumer()
    )
    
    # Guaranteed cleanup
    await scope.close()

asyncio.run(main())
```

**Output:**
```
Result: 2
Result: 4  
Result: 6
Result: 8
Result: 10
```

## Core Concepts

**effectpy** is built around a few key abstractions:

| Concept | Purpose | Key Benefits |
|---------|---------|-------------|
| **Effect[R, E, A]** | Composable async computation | Type-safe errors, resource requirements |
| **Context** | Dependency injection | Testable, modular services |
| **Scope** | Resource lifecycle | Guaranteed cleanup, no leaks |
| **Layer** | Resource construction | Composable, reusable environments |
| **Fiber** | Lightweight async task | Structured cancellation, supervision |
| **Stream** | Functional data processing | Backpressure, error channels |

## Getting Started

<div class="grid cards" markdown>

-   :material-download:{ .lg .middle } **Installation**

    ---

    Install effectpy and optional dependencies

    [:octicons-arrow-right-24: Installation guide](installation.md)

-   :material-rocket-launch:{ .lg .middle } **Quick Start**

    ---

    Build your first effectpy application

    [:octicons-arrow-right-24: Quick start tutorial](quickstart.md)

-   :material-school:{ .lg .middle } **Core Concepts**

    ---

    Understand Effects, Layers, Scopes, and more

    [:octicons-arrow-right-24: Learn the concepts](concepts/effects.md)

-   :material-code-braces:{ .lg .middle } **API Reference**

    ---

    Detailed API documentation and examples

    [:octicons-arrow-right-24: Browse the API](reference/effectpy.md)

</div>
