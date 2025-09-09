---
title: effectpy
description: Effect-inspired structured async for Python with guaranteed resource safety, rich error handling, and built-in observability
---

![effectpy logo](https://raw.githubusercontent.com/stukennedy/effectpy/main/img/effectpy.png)

# effectpy

**Effect-inspired structured async for Python**

**Quick Links:** [📦 Get Started](installation.md) | [🚀 Quick Start](quickstart.md) | [💻 View on GitHub](https://github.com/stukennedy/effectpy)

## Why effectpy?

`asyncio` is powerful but messy: exceptions leak, cancellations are tricky, resources are forgotten, and observability is bolted on later. **effectpy** brings the battle-tested semantics of [Effect TS](https://effect.website) and [ZIO](https://zio.dev) to Python.

### ✅ **Guaranteed Resource Safety**
Every resource is automatically cleaned up in the correct order, even when errors occur or operations are cancelled.

**→ [Learn about Layers & Scope](concepts/layers_scope.md)**

### ⚡ **Structured Concurrency**  
Race, zip, and parallelize operations with deterministic cancellation. No more leaked tasks or zombie coroutines.

**→ [Explore concurrency patterns](guides/concurrency.md)**

### 🐛 **Rich Error Handling**
Failures are first-class citizens with structured `Cause` trees, annotations, and stack traces. No more mysterious exceptions.

**→ [Understanding Effects](concepts/effects.md)**

### 👁️ **Built-in Observability**
Automatic logging, metrics, and tracing with OpenTelemetry integration. Understand your async code's behavior.

**→ [Observability guide](concepts/observability.md)**

### 🔧 **Streaming & Pipelines**
Process data streams with backpressure, error channels, and parallel stages. Built for real-world data processing.

**→ [Streams & Channels](concepts/streams_channels.md)**

### 🧪 **Test-Friendly**
Deterministic test clocks, controllable time, and supervision make testing async code predictable.

**→ [Testing patterns](guides/concurrency.md#testing-with-testclock)**

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

### 📦 **Installation**  
Install effectpy and optional dependencies

**→ [Installation guide](installation.md)**

### 🚀 **Quick Start**
Build your first effectpy application  

**→ [Quick start tutorial](quickstart.md)**

### 📚 **Core Concepts**
Understand Effects, Layers, Scopes, and more

**→ [Learn the concepts](concepts/effects.md)**

### 📖 **API Reference**  
Detailed API documentation and examples

**→ [Browse the API](reference/effectpy.md)**
