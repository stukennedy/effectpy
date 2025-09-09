from __future__ import annotations
import asyncio
from typing import Awaitable, Callable, Generic, Iterable, List, Optional, TypeVar

from .queue import Queue, QueueClosed
from .channel import Channel as _Channel
from .core import Effect, succeed
from .context import Context
from .scope import Scope

A = TypeVar("A")
B = TypeVar("B")


class Stage(Generic[A, B]):
    def __init__(self, func: Callable[[A], Awaitable[B]], workers: int = 1, out_capacity: int = 0):
        self.func = func
        self.workers = max(1, workers)
        self.out_capacity = max(0, out_capacity)


class Stream(Generic[A]):
    """Minimal stream built atop Queue with termination propagation.

    A Stream is a function that, given an output Queue, runs producers/tasks that
    write to it and then closes it when done.
    """

    def __init__(self, build: Callable[[Queue[A]], Effect[object, Exception, None]]):
        self._build = build

    @staticmethod
    def from_iterable(items: Iterable[A], out_capacity: int = 0) -> "Stream[A]":
        def build(out: Queue[A]) -> Effect[object, Exception, None]:
            async def run(_: Context):
                try:
                    for it in items:
                        await out.send(it)
                finally:
                    await out.close()
                return None
            return Effect(run)

        return Stream(build)

    def via(self, stage: Stage[A, B]) -> "Stream[B]":
        def build(out: Queue[B]) -> Effect[object, Exception, None]:
            async def run(ctx: Context):
                # Intermediate queue between upstream and this stage
                in_q: Queue[A] = Queue(maxsize=stage.out_capacity)

                # Start upstream to feed in_q
                upstream = self._build(in_q)
                asyncio.create_task(upstream._run(ctx))

                active = {"n": stage.workers}
                close_lock = asyncio.Lock()
                closed_flag = {"v": False}

                async def close_out_once():
                    async with close_lock:
                        if not closed_flag["v"]:
                            closed_flag["v"] = True
                            await out.close()

                async def worker():
                    while True:
                        try:
                            x = await in_q.receive()
                        except QueueClosed:
                            # Upstream finished; last worker closes downstream
                            active["n"] -= 1
                            if active["n"] == 0:
                                await close_out_once()
                            return
                        try:
                            y = await stage.func(x)
                        except BaseException:
                            # On error: close downstream and signal upstream by closing in_q
                            await close_out_once()
                            await in_q.close()
                            return
                        try:
                            await out.send(y)
                        except QueueClosed:
                            # Downstream closed early; stop processing
                            await in_q.close()
                            return

                for _ in range(stage.workers):
                    asyncio.create_task(worker())

                # Allow tasks to start
                await asyncio.sleep(0)
                return None

            return Effect(run)

        return Stream(build)

    def to_queue(self, out: Queue[A]) -> Effect[object, Exception, None]:
        return self._build(out)

    def run_collect(self) -> Effect[object, Exception, List[A]]:
        async def run(ctx: Context):
            out: Queue[A] = Queue()
            # Start the stream pumping into out
            asyncio.create_task(self._build(out)._run(ctx))

            # Collect until closed
            results: List[A] = []
            while True:
                try:
                    v = await out.receive()
                    results.append(v)
                except QueueClosed:
                    break
            return results

        return Effect(run)

    # Convenience: map with a sync function
    def map(self, f: Callable[[A], B]) -> "Stream[B]":
        async def mapper(x: A) -> B:
            return f(x)

        return self.via(stream_stage(mapper, workers=1))

    # Buffer by inserting an identity stage with desired capacity
    def buffer(self, capacity: int) -> "Stream[A]":
        async def ident(x: A) -> A:
            return x

        return self.via(stream_stage(ident, workers=1, out_capacity=max(0, capacity)))

    # Merge two streams into one; both run concurrently and share the same output
    def merge(self, other: "Stream[A]") -> "Stream[A]":
        def build(out: Queue[A]) -> Effect[object, Exception, None]:
            async def run(ctx: Context):
                q1: Queue[A] = Queue()
                q2: Queue[A] = Queue()

                # Start upstreams pumping into q1 and q2
                asyncio.create_task(self._build(q1)._run(ctx))
                asyncio.create_task(other._build(q2)._run(ctx))

                async def pump(src: Queue[A]):
                    while True:
                        try:
                            v = await src.receive()
                        except QueueClosed:
                            return
                        try:
                            await out.send(v)
                        except QueueClosed:
                            return

                t1 = asyncio.create_task(pump(q1))
                t2 = asyncio.create_task(pump(q2))
                await asyncio.gather(t1, t2)
                await out.close()
                return None

            return Effect(run)

        return Stream(build)

    # Sinks: run_fold to aggregate items
    def run_fold(self, initial: B, f: Callable[[B, A], B]) -> Effect[object, Exception, B]:
        async def run(ctx: Context):
            out: Queue[A] = Queue()
            asyncio.create_task(self._build(out)._run(ctx))
            acc: B = initial
            while True:
                try:
                    v = await out.receive()
                except QueueClosed:
                    break
                acc = f(acc, v)
            return acc

        return Effect(run)


def stream_stage(func: Callable[[A], Awaitable[B]], workers: int = 1, out_capacity: int = 0) -> Stage[A, B]:
    return Stage(func, workers, out_capacity)

# --- Error-channel Streams and Sinks ---

E = TypeVar("E")


class Sink(Generic[A, B]):
    def __init__(self, run_impl: Callable[[Queue[A], Queue[BaseException], Context], Awaitable[B]]):
        self._run_impl = run_impl

    async def _run(self, out: Queue[A], err: Queue[BaseException], ctx: Context) -> B:
        return await self._run_impl(out, err, ctx)


class StreamE(Generic[A]):
    def __init__(self, build: Callable[[Queue[A], Queue[BaseException]], Effect[object, Exception, None]]):
        self._build = build

    @staticmethod
    def from_iterable(items: Iterable[A]) -> "StreamE[A]":
        def build(out: Queue[A], err: Queue[BaseException]) -> Effect[object, Exception, None]:
            async def run(_: Context) -> None:
                try:
                    for it in items:
                        await out.send(it)
                except BaseException as ex:
                    await err.send(ex)
                finally:
                    await out.close()
                return None
            return Effect(run)

        return StreamE(build)

    def via_effect(self, func: Callable[[A], Effect[object, Exception, B]], workers: int = 1, out_capacity: int = 0) -> "StreamE[B]":
        def build(out: Queue[B], err: Queue[BaseException]) -> Effect[object, Exception, None]:
            async def run(ctx: Context):
                in_q: Queue[A] = Queue(maxsize=out_capacity)
                asyncio.create_task(self._build(in_q, err)._run(ctx))

                active = {"n": max(1, workers)}
                close_lock = asyncio.Lock()
                closed_flag = {"v": False}

                async def close_out_once():
                    async with close_lock:
                        if not closed_flag["v"]:
                            closed_flag["v"] = True
                            await out.close()

                async def worker():
                    while True:
                        try:
                            x = await in_q.receive()
                        except QueueClosed:
                            active["n"] -= 1
                            if active["n"] == 0:
                                await close_out_once()
                            return
                        try:
                            eff = func(x)
                            y = await eff._run(ctx)
                        except BaseException as ex:
                            await err.send(ex)
                            await in_q.close(); await close_out_once(); return
                        try:
                            await out.send(y)
                        except QueueClosed:
                            await in_q.close(); return

                for _ in range(max(1, workers)):
                    asyncio.create_task(worker())

                await asyncio.sleep(0)
                return None
            return Effect(run)
        return StreamE(build)

    # Convenience: pure map via effect
    def map(self, f: Callable[[A], B], workers: int = 1, out_capacity: int = 0) -> "StreamE[B]":
        def eff(x: A) -> Effect[object, Exception, B]:
            return succeed(f(x))

        return self.via_effect(eff, workers=workers, out_capacity=out_capacity)

    # Buffer via identity stage
    def buffer(self, capacity: int) -> "StreamE[A]":
        def eff(x: A) -> Effect[object, Exception, A]:
            return succeed(x)

        return self.via_effect(eff, workers=1, out_capacity=max(0, capacity))

    def filter(self, p: Callable[[A], bool]) -> "StreamE[A]":
        def build(out: Queue[A], err: Queue[BaseException]) -> Effect[object, Exception, None]:
            async def run(ctx: Context):
                in_q: Queue[A] = Queue()
                asyncio.create_task(self._build(in_q, err)._run(ctx))
                async def worker():
                    while True:
                        try:
                            x = await in_q.receive()
                        except QueueClosed:
                            await out.close(); return
                        try:
                            if p(x):
                                await out.send(x)
                        except QueueClosed:
                            await in_q.close(); return
                        except BaseException as ex:
                            await err.send(ex); await in_q.close(); await out.close(); return
                asyncio.create_task(worker()); await asyncio.sleep(0); return None
            return Effect(run)
        return StreamE(build)

    def take(self, n: int) -> "StreamE[A]":
        n = max(0, n)
        def build(out: Queue[A], err: Queue[BaseException]) -> Effect[object, Exception, None]:
            async def run(ctx: Context):
                in_q: Queue[A] = Queue()
                asyncio.create_task(self._build(in_q, err)._run(ctx))
                remaining = {"n": n}
                async def worker():
                    while True:
                        if remaining["n"] <= 0:
                            await in_q.close(); await out.close(); return
                        try:
                            x = await in_q.receive()
                        except QueueClosed:
                            await out.close(); return
                        try:
                            await out.send(x)
                        except QueueClosed:
                            await in_q.close(); return
                        remaining["n"] -= 1
                        if remaining["n"] <= 0:
                            await in_q.close(); await out.close(); return
                asyncio.create_task(worker()); await asyncio.sleep(0); return None
            return Effect(run)
        return StreamE(build)

    def timeout(self, seconds: float) -> "StreamE[A]":
        def build(out: Queue[A], err: Queue[BaseException]) -> Effect[object, Exception, None]:
            async def run(ctx: Context):
                in_q: Queue[A] = Queue()
                asyncio.create_task(self._build(in_q, err)._run(ctx))
                async def worker():
                    while True:
                        try:
                            x = await asyncio.wait_for(in_q.receive(), timeout=max(0.0, seconds))
                        except asyncio.TimeoutError as ex:
                            await err.send(ex); await in_q.close(); await out.close(); return
                        except QueueClosed:
                            await out.close(); return
                        try:
                            await out.send(x)
                        except QueueClosed:
                            await in_q.close(); return
                asyncio.create_task(worker()); await asyncio.sleep(0); return None
            return Effect(run)
        return StreamE(build)

    def throttle(self, period: float) -> "StreamE[A]":
        period = max(0.0, period)
        def build(out: Queue[A], err: Queue[BaseException]) -> Effect[object, Exception, None]:
            async def run(ctx: Context):
                in_q: Queue[A] = Queue()
                asyncio.create_task(self._build(in_q, err)._run(ctx))
                async def worker():
                    while True:
                        try:
                            x = await in_q.receive()
                        except QueueClosed:
                            await out.close(); return
                        await asyncio.sleep(period)
                        try:
                            await out.send(x)
                        except QueueClosed:
                            await in_q.close(); return
                asyncio.create_task(worker()); await asyncio.sleep(0); return None
            return Effect(run)
        return StreamE(build)

    def merge(self, other: "StreamE[A]") -> "StreamE[A]":
        def build(out: Queue[A], err: Queue[BaseException]) -> Effect[object, Exception, None]:
            async def run(ctx: Context):
                q1: Queue[A] = Queue(); q2: Queue[A] = Queue()
                asyncio.create_task(self._build(q1, err)._run(ctx))
                asyncio.create_task(other._build(q2, err)._run(ctx))
                async def pump(src: Queue[A]):
                    while True:
                        try:
                            v = await src.receive()
                        except QueueClosed:
                            return
                        try:
                            await out.send(v)
                        except QueueClosed:
                            return
                await asyncio.gather(asyncio.create_task(pump(q1)), asyncio.create_task(pump(q2)))
                await out.close(); return None
            return Effect(run)
        return StreamE(build)

    def run(self, sink: Sink[A, B]) -> Effect[object, Exception, B]:
        async def run(ctx: Context):
            out: Queue[A] = Queue(); err: Queue[BaseException] = Queue()
            asyncio.create_task(self._build(out, err)._run(ctx))
            return await sink._run(out, err, ctx)
        return Effect(run)

    @staticmethod
    def from_channel(src: _Channel[A]) -> "StreamE[A]":
        def build(out: Queue[A], err: Queue[BaseException]) -> Effect[object, Exception, None]:
            async def run(_: Context) -> None:
                # Unbounded forwarder: no close signal; mirrors Channel semantics
                while True:
                    v = await src.receive()
                    try:
                        await out.send(v)
                    except QueueClosed:
                        # downstream closed; drop
                        return None
            return Effect(run)
        return StreamE(build)

    # Resource-scoped stage: acquire once per worker, release on termination
    def via_acquire_release(self,
                            acquire: Effect[object, Exception, B],
                            release: Callable[[B], Effect[object, Exception, None]],
                            func: Callable[[B, A], Effect[object, Exception, C]],
                            workers: int = 1,
                            out_capacity: int = 0
                            ) -> "StreamE[C]":
        C_ = TypeVar('C')  # type: ignore
        # Use names B and C from outer TypeVars; typing workaround for runtime
        def build(out: Queue[C], err: Queue[BaseException]) -> Effect[object, Exception, None]:  # type: ignore[name-defined]
            async def run(ctx: Context):
                in_q: Queue[A] = Queue(maxsize=out_capacity)
                asyncio.create_task(self._build(in_q, err)._run(ctx))

                active = {"n": max(1, workers)}
                close_lock = asyncio.Lock()
                closed_flag = {"v": False}

                async def close_out_once():
                    async with close_lock:
                        if not closed_flag["v"]:
                            closed_flag["v"] = True
                            await out.close()

                async def worker():
                    try:
                        rsrc = await acquire._run(ctx)
                    except BaseException as ex:
                        await err.send(ex)
                        # Cannot proceed; treat as worker termination
                        active["n"] -= 1
                        if active["n"] == 0:
                            await close_out_once()
                        return
                    try:
                        while True:
                            try:
                                x = await in_q.receive()
                            except QueueClosed:
                                active["n"] -= 1
                                if active["n"] == 0:
                                    await close_out_once()
                                return
                            try:
                                y = await func(rsrc, x)._run(ctx)
                            except BaseException as ex:
                                await err.send(ex)
                                await in_q.close(); await close_out_once(); return
                            try:
                                await out.send(y)
                            except QueueClosed:
                                await in_q.close(); return
                    finally:
                        try:
                            await release(rsrc)._run(ctx)  # type: ignore[name-defined]
                        except BaseException:
                            pass

                for _ in range(max(1, workers)):
                    asyncio.create_task(worker())
                await asyncio.sleep(0)
                return None
            return Effect(run)
        return StreamE(build)

    def run_scoped(self, sink: Sink[A, B], scope: Scope) -> Effect[object, Exception, B]:
        async def run(ctx: Context):
            out: Queue[A] = Queue(); err: Queue[BaseException] = Queue()
            asyncio.create_task(self._build(out, err)._run(ctx))
            try:
                return await sink._run(out, err, ctx)
            finally:
                # Ensure downstream queues are closed to signal termination to all tasks
                try:
                    await out.close()
                finally:
                    await err.close()
        return Effect(run)


def sink_fold(initial: B, f: Callable[[B, A], B]) -> Sink[A, B]:
    async def run(out: Queue[A], err: Queue[BaseException], _ctx: Context) -> B:
        CLOSED = object()
        async def recv_safe(q: Queue[Any]):
            try:
                return await q.receive()
            except QueueClosed:
                return CLOSED
        acc: B = initial
        while True:
            t_val = asyncio.create_task(recv_safe(out))
            t_err = asyncio.create_task(recv_safe(err))
            done, pending = await asyncio.wait({t_val, t_err}, return_when=asyncio.FIRST_COMPLETED)
            for p in pending:
                p.cancel()
            # Ensure canceled tasks are awaited to avoid warnings
            for p in pending:
                try:
                    await p
                except BaseException:
                    pass
            # Prioritize error if both somehow completed
            d = t_err if t_err in done else t_val
            try:
                v = await d
            except QueueClosed:
                # Before concluding completion, check if an error is pending
                t_try_err = asyncio.create_task(recv_safe(err))
                done2, pending2 = await asyncio.wait({t_try_err}, timeout=0)
                for p in pending2:
                    p.cancel()
                    try:
                        await p
                    except BaseException:
                        pass
                if done2:
                    err_val = await t_try_err
                    if err_val is not CLOSED and isinstance(err_val, BaseException):
                        raise err_val
                return acc
            if d is t_err:
                if v is not CLOSED and isinstance(v, BaseException):
                    raise v
                raise RuntimeError("unknown stream error")
            if v is CLOSED:
                return acc
            acc = f(acc, v)
            # If the other task also completed, await it to consume exceptions
            other = t_val if d is t_err else t_err
            if other in done:
                try:
                    await other
                except BaseException:
                    pass
    return Sink(run)


def sink_head() -> Sink[A, Optional[A]]:
    async def run(out: Queue[A], err: Queue[BaseException], _ctx: Context) -> Optional[A]:
        CLOSED = object()
        async def recv_safe(q: Queue[Any]):
            try:
                return await q.receive()
            except QueueClosed:
                return CLOSED
        while True:
            t_val = asyncio.create_task(recv_safe(out))
            t_err = asyncio.create_task(recv_safe(err))
            done, pending = await asyncio.wait({t_val, t_err}, return_when=asyncio.FIRST_COMPLETED)
            for p in pending:
                p.cancel()
                try:
                    await p
                except BaseException:
                    pass
            d = t_err if t_err in done else t_val
            try:
                v = await d
            except QueueClosed:
                # Completed empty
                return None
            if d is t_err:
                if v is not CLOSED and isinstance(v, BaseException):
                    raise v
                raise RuntimeError("unknown stream error")
            if v is CLOSED:
                return None
            return v
            # If the other task also completed, await it to consume exceptions
            other = t_val if d is t_err else t_err
            if other in done:
                try:
                    await other
                except BaseException:
                    pass
    return Sink(run)


def sink_drain() -> Sink[A, None]:
    async def run(out: Queue[A], err: Queue[BaseException], _ctx: Context) -> None:
        CLOSED = object()
        async def recv_safe(q: Queue[Any]):
            try:
                return await q.receive()
            except QueueClosed:
                return CLOSED
        while True:
            t_val = asyncio.create_task(recv_safe(out))
            t_err = asyncio.create_task(recv_safe(err))
            done, pending = await asyncio.wait({t_val, t_err}, return_when=asyncio.FIRST_COMPLETED)
            for p in pending:
                p.cancel()
                try:
                    await p
                except BaseException:
                    pass
            d = t_err if t_err in done else t_val
            try:
                v = await d
            except QueueClosed:
                return None
            if d is t_err:
                # Error channel produced
                if v is CLOSED:
                    # Error queue closed; treat as normal completion
                    return None
                if isinstance(v, BaseException):
                    raise v
                # Unexpected payload on error channel; ignore and continue
                continue
            # Value channel: if closed, we are done
            if v is CLOSED:
                return None
            # else just discard and continue
            other = t_val if d is t_err else t_err
            if other in done:
                try:
                    await other
                except BaseException:
                    pass
    return Sink(run)
