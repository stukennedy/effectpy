# effectpy Reference

The `effectpy` package provides all the core functionality for structured async programming in Python. This page documents the main exports and their usage.

## Quick Import Reference

```python
from effectpy import *
```

This imports all the essential components:

### Core Effects

| Import | Purpose |
|--------|---------|
| `Effect` | The main Effect monad |
| `succeed`, `fail` | Create successful/failed effects |
| `from_async`, `sync` | Convert async/sync functions to effects |
| `attempt` | Safely wrap functions that may throw |

### Composition

| Import | Purpose |
|--------|---------|
| `zip_par` | Run effects in parallel, wait for all |
| `race` | Run effects in parallel, return first |
| `for_each_par` | Map over collections in parallel |

### Resource Management

| Import | Purpose |
|--------|---------|
| `Context`, `Scope` | Service container and resource lifecycle |
| `Layer`, `from_resource` | Resource builders |
| `acquire_release` | Safe resource acquisition pattern |

### Runtime & Concurrency

| Import | Purpose |
|--------|---------|
| `Runtime`, `Fiber` | asyncio-based execution runtime |
| `AnyIORuntime`, `AnyIOFiber` | AnyIO/Trio runtime (optional) |

### Streaming

| Import | Purpose |
|--------|---------|  
| `Stream`, `StreamE` | Functional streams with error channels |
| `Channel` | Async communication channels |
| `Pipeline`, `stage` | Staged data processing pipelines |

### Observability

| Import | Purpose |
|--------|---------|
| `instrument` | Add automatic logging/metrics/tracing |
| `LoggerLayer`, `MetricsLayer`, `TracerLayer` | Observability services |
| `export_spans_otlp_http`, `export_metrics_otlp_http` | OTLP exporters |

### Utilities

| Import | Purpose |
|--------|---------|
| `Schedule` | Retry/repeat policies |
| `Deferred`, `Ref`, `Queue` | Async primitives |
| `FiberRef` | Fiber-local storage |
| `Hub` | Publish-subscribe messaging |

### Data Types

| Import | Purpose |
|--------|---------|
| `Option`, `Some`, `NONE` | Optional values |
| `Either`, `Left`, `Right` | Sum types |
| `Result`, `Ok`, `Err` | Result with error handling |
| `Duration` | Time durations |
| `Chunk` | Immutable collections |

## Core API

::: effectpy.core
    options:
      show_source: false
      heading_level: 3
      
## Context & Resource Management

::: effectpy.context
    options:
      show_source: false
      heading_level: 3

::: effectpy.scope  
    options:
      show_source: false
      heading_level: 3

::: effectpy.layer
    options:
      show_source: false  
      heading_level: 3

## Concurrency & Runtime

::: effectpy.runtime
    options:
      show_source: false
      heading_level: 3

## Streaming & Pipelines

::: effectpy.channel
    options:
      show_source: false
      heading_level: 3

::: effectpy.stream
    options:
      show_source: false
      heading_level: 3

::: effectpy.pipeline
    options:
      show_source: false
      heading_level: 3

## Observability

::: effectpy.instrument
    options:
      show_source: false
      heading_level: 3

::: effectpy.logger
    options:
      show_source: false
      heading_level: 3

::: effectpy.metrics
    options:
      show_source: false
      heading_level: 3

::: effectpy.tracer
    options:
      show_source: false
      heading_level: 3

## Data Types

::: effectpy.option
    options:
      show_source: false
      heading_level: 3

::: effectpy.either
    options:
      show_source: false
      heading_level: 3

::: effectpy.result
    options:
      show_source: false
      heading_level: 3

