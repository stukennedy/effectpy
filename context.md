# EffectPy – LLM Context Guide

Goal: give an agent/LLM everything needed to write, run, and extend code against this repo without installing the package. Focus on the primitives, common patterns, and gotchas.

## Mental Model

- EffectPy brings Effect/ZIO-style structured async to Python.
- Core value type: `Effect[R, E, A]` — an async computation that:
  - Runs with an environment `R` (via a `Context` holding services),
  - May fail with error type `E` (wrapped in `Failure`/`Cause`),
  - Yields a value of type `A`.
- Compose effects (`map`, `flat_map`), recover (`catch_all`), provide dependencies (`provide`), and run them via a `Runtime` or plain `await eff._run(ctx)`.

## Repository Map

- `effectpy/core.py`: `Effect`, `Exit`, `Cause`, `Failure`; constructors/utilities: `succeed`, `fail`, `from_async`, `sync`, `attempt`, `uninterruptible`, `uninterruptibleMask`, `annotate_cause`.
- `effectpy/context.py`: `Context` (DI container) with `get` and `add`.
- `effectpy/scope.py`: `Scope` to register async finalizers, `close()` is LIFO.
- `effectpy/layer.py`: `Layer` abstraction and `from_resource`; compose with `+` (sequential) or `|` (parallel merge).
- `effectpy/runtime.py`: asyncio `Runtime` and `Fiber` (fork/join/interruption).
- `effectpy/anyio_runtime.py`: optional AnyIO/Trio `AnyIORuntime`/`AnyIOFiber` (import guarded).
- `effectpy/logger.py`, `effectpy/metrics.py`, `effectpy/tracer.py`: built-in observability services and layers.
- `effectpy/instrument.py`: `instrument(name, eff, tags)` wrapper that logs, traces and records a duration histogram.
- `effectpy/channel.py`: simple async `Channel` built on `asyncio.Queue`.
- `effectpy/pipeline.py`: `Pipeline` with parallel `stage()` workers and backpressure via channels.
- `effectpy/exporters.py`: optional OTLP HTTP exporters (no-op if `aiohttp` missing).
- `examples/*`: runnable examples (module form).
- `tests/*`: unit tests covering the above.

## Quick Start (in this repo)

- Run examples without installing:
  - `python -m examples.basic_effects` (or `uv run python -m examples.basic_effects`)
  - Alternative file-path form: `PYTHONPATH=. python examples/basic_effects.py`
- Run tests:
  - `python -m unittest discover -s tests -p 'test_*.py' -v`
  - or `uv run python -m unittest discover -s tests -p 'test_*.py' -v`
- Make targets (uv-based): `make examples-list`, `make example-basic`, `make test`.

## Core API Cheatsheet

- Create effects
  - `succeed(a)` — pure success
  - `fail(e)` — typed failure (raises `Failure(e)` under the hood)
  - `from_async(thunk)` — wrap `await`able
  - `sync(thunk)` — wrap sync function
  - `attempt(thunk, on_error)` — run sync `thunk`; on exception, raise `Failure(on_error(exc))`
- Compose
  - `eff.map(f)`, `eff.flat_map(lambda a: eff2)`, `eff.catch_all(handler)`
  - `eff.provide(layer)` — run with additional environment managed by `layer`
- Run
  - Direct: `await eff._run(ctx)`
  - With runtime: `rt = Runtime(ctx)`, `await rt.run(eff)`; `fiber = rt.fork(eff)`; `await fiber.await_()`
- Results & errors
  - `Fiber.await_()` returns `Exit(success=True, value=...)` or `Exit(success=False, cause=Cause.*)`
  - `Cause` kinds: `fail(error)`, `die(exception)`, `interrupt()`, plus combinators `both`, `then`
  - `annotate_cause(cause, note)` to add notes
- Cancellation
  - `uninterruptible(eff)`: best-effort finish-on-cancel; in asyncio exact ZIO semantics are tricky. Don’t rely on full masking semantics.

## Environment and Resources

- `Context`: DI map from `type -> instance`.
  - `ctx.get(ServiceType)` retrieves a service; raises `KeyError` if missing.
  - `ctx.add(ServiceType, instance)` returns a new `Context` with the service bound.
- `Layer` for acquisition/teardown
  - Build from resource: `from_resource(ServiceType, mk_async, close_async)`
  - Compose: `L1 + L2` (sequential dependency), `L1 | L2` (parallel acquire + merged context)
  - Use `build_scoped(base_ctx, scope)` so resources are auto-released via `scope.close()`
- `Scope`
  - `await scope.add_finalizer(async_fn)` and `await scope.close()` (LIFO; exceptions are swallowed — consider logging in your app code if needed).

Example: defining and using a resource

```python
import asyncio
from effectpy import Context, Scope, from_resource, LoggerLayer

class DB:
    async def query(self, x: int) -> int:
        await asyncio.sleep(0.01)
        return x * 2

async def mk_db(_): return DB()
async def close_db(_): return None
DBLayer = from_resource(DB, mk_db, close_db)

async def main():
    base, scope = Context(), Scope()
    env = await (LoggerLayer | DBLayer).build_scoped(base, scope)
    db = env.get(DB)
    print(await db.query(21))
    await scope.close()
```

## Observability

- Services: `ConsoleLogger`, `MetricsRegistry`, `Tracer`; layers: `LoggerLayer`, `MetricsLayer`, `TracerLayer`.
- Wrap any effect: `instrument("name", eff, tags={"k":"v"})`
  - Logs start/end, records a duration histogram, and emits a span in `Tracer`.
  - Note: metric names include tag values (cardinality risk); keep tag sets small.
- Export (optional):
  - `await export_spans_otlp_http(tracer, endpoint)`
  - `await export_metrics_otlp_http(metrics, endpoint)`
  - No-op if `aiohttp` is not installed.

## Concurrency

- `Runtime` (asyncio):
  - `rt = Runtime(env)`, `fiber = rt.fork(eff)`, `exit = await fiber.await_()`, `fiber.interrupt()`
- AnyIO/Trio (optional):
  - `from effectpy.anyio_runtime import AnyIORuntime`
  - Use as `async with AnyIORuntime(env) as rt: fiber = await rt.fork(eff)`
  - Only available if `anyio` is installed.

## Channels and Pipelines

- `Channel[T](maxsize=0)`: `await ch.send(x)`, `await ch.receive()`, `await ch.close()` (close prevents further sends; it does not unblock receivers).
- `Pipeline`:
  - Build: `Pipeline(src).via(stage(fn, workers=2, out_capacity=4)).to_channel(out)`
  - Returns an `Effect` that wires channel workers and a final pump. It doesn’t auto-shutdown; manage lifecycle outside (e.g., send a known number of items and stop consumers after that many). Avoid using in long-lived processes without a clear stop plan.

## Patterns an LLM Should Prefer

- Always run effects with a `Context` that has required services; use layers to build it.
- Prefer module form when running examples from this repo: `python -m examples.name` so the local `effectpy` is on `sys.path`.
- Use `from_resource` + `Scope` for resources; call `await scope.close()` when done.
- For observability, wrap with `instrument`. Keep tag cardinality low.
- Don’t reach into private fields like `Context._values`. Use `get/add` and layer composition.
- Treat `uninterruptible` as best-effort; if you need strict masking semantics, design co-operative cancellation.

## Common Gotchas

- Running examples by file path without `PYTHONPATH=.` will fail to import `effectpy`. Use module form or set `PYTHONPATH`.
- `Channel.close()` does not signal receivers; design your protocol (e.g., send sentinel values or count-based consumption).
- `Pipeline` currently leaks tasks if upstream/consumer stop; design stop conditions explicitly.
- `AnyIORuntime` is optional; guard imports or rely on `effectpy.__init__` which sets it to `None` when missing.

## Useful Snippets

Compose and recover:
```python
from effectpy import succeed, fail
ok = succeed(1).map(lambda x: x+1)              # 2
rescue = fail("boom").catch_all(lambda e: succeed(f"handled:{e}"))
```

Provide dependencies locally:
```python
from effectpy import Effect, LoggerLayer, Context
async def hello(ctx: Context):
    from effectpy import ConsoleLogger
    await ctx.get(ConsoleLogger).info("hi")
    return "ok"
res = await Effect(hello).provide(LoggerLayer)._run(Context())
```

Fork and await fibers:
```python
from effectpy import Runtime, Effect, Context
rt = Runtime(Context())
fa = rt.fork(Effect(lambda _: some_async()))
ex = await fa.await_()
if ex.success: print(ex.value)
else: print(ex.cause.kind)
```

## How to Publish (summary)

- Version in `pyproject.toml` → `uv build` → `uvx twine check dist/*` → `uvx twine upload dist/*` (or `--repository testpypi`). See README for details.

---
This file is designed for codegen agents. Prefer the patterns above, keep changes minimal, and follow existing styles (e.g., use layers and contexts, avoid private fields).

