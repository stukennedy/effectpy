from __future__ import annotations
from typing import TypeVar
from .core import Effect, Failure
from .context import Context
from .logger import ConsoleLogger
from .metrics import MetricsRegistry
from .tracer import Tracer

A = TypeVar('A'); E = TypeVar('E'); R = TypeVar('R')

def instrument(name: str, eff: Effect[R, E, A], tags: dict[str, str] | None = None) -> Effect[R, E, A]:
    async def run(ctx: Context):
        logger = None; metrics=None; tracer=None
        try: logger = ctx.get(ConsoleLogger)
        except KeyError: pass
        try: metrics = ctx.get(MetricsRegistry)
        except KeyError: pass
        try: tracer = ctx.get(Tracer)
        except KeyError: pass

        tag_suffix = '' if not tags else '_' + '_'.join([f"{k}={v}" for k,v in sorted(tags.items())])
        span=None
        if tracer:
            span = await tracer.start_span(name)
            span.name = name + (" " + ", ".join([f"{k}={v}" for k,v in sorted(tags.items())]) if tags else "")
        if logger: await logger.info(f"start {name}")  # type: ignore
        import time as _t; t0=_t.time()
        try:
            res = await eff._run(ctx)
            return res
        except Failure as fe:
            if logger: await logger.error(f"fail {name}: {fe.error}")  # type: ignore
            if tracer and span: await tracer.end_span(span, status="ERROR", error=str(fe.error))
            raise
        except BaseException as ex:
            if logger: await logger.error(f"die {name}: {ex}")  # type: ignore
            if tracer and span: await tracer.end_span(span, status="DIE", error=str(ex))
            raise
        finally:
            t1=_t.time()
            if tracer and span and span.end is None: await tracer.end_span(span, status="OK")
            if metrics:
                h = await metrics.histogram(f"effect_duration_seconds_{name}{tag_suffix}", help=f"Duration of effect {name}")
                h.observe(max(0.0, t1-t0))
            if logger: await logger.info(f"end {name}")  # type: ignore
    return Effect(run)
