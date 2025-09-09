from __future__ import annotations
from dataclasses import dataclass
import contextvars
from typing import Awaitable, Callable, Generic, TypeVar, Any, Optional, Protocol, runtime_checkable, Iterable, Tuple, List
import asyncio
from .schedule import Schedule
from .scope import Scope

R = TypeVar("R"); E = TypeVar("E"); A = TypeVar("A"); B = TypeVar("B"); E2 = TypeVar("E2")

@dataclass
class Exit(Generic[E, A]):
    success: bool
    value: Optional[A] = None
    cause: Optional["Cause[E]"] = None

class Failure(Exception, Generic[E]):
    def __init__(self, error: E, annotations: Optional[list[str]] = None):
        super().__init__(repr(error)); self.error = error; self.annotations = list(annotations or [])

@runtime_checkable
class _LayerLike(Protocol):
    async def build(self, parent: "Context") -> "Context": ...
    async def teardown(self, ctx: "Context") -> None: ...

@dataclass(frozen=True)
class Cause(Generic[E]):
    kind: str
    left: Optional["Cause[E]"] = None
    right: Optional["Cause[E]"] = None
    error: Optional[E] = None
    defect: Optional[BaseException] = None
    annotations: list[str] = None

    def render(self, indent: str = "", include_traces: bool = True) -> str:
        def line(s: str) -> str: return indent + s + "\n"
        notes = ""
        if self.annotations:
            for n in self.annotations: notes += line("@ " + n)
        if self.kind == 'fail': return notes + line(f"Fail({self.error!r})")
        if self.kind == 'die':
            s = notes + line(f"Die({self.defect!r})")
            if include_traces and self.defect and self.defect.__traceback__:
                tb = ''.join(__import__('traceback').format_exception(type(self.defect), self.defect, self.defect.__traceback__))
                s += ''.join(indent + '  ' + l for l in tb.splitlines(True))
            return s
        if self.kind == 'interrupt': return notes + line("Interrupt")
        if self.kind in ('both','then'):
            op = 'Both' if self.kind == 'both' else 'Then'
            l = self.left.render(indent + "  ", include_traces) if self.left else indent+"  (empty)\n"
            r = self.right.render(indent + "  ", include_traces) if self.right else indent+"  (empty)\n"
            return notes + line(op + ":") + l + r
        return notes + line(f"Unknown({self.kind})")

    @staticmethod
    def fail(e: E) -> "Cause[E]": return Cause(kind='fail', error=e, annotations=[])
    @staticmethod
    def die(ex: BaseException) -> "Cause[E]": return Cause(kind='die', defect=ex, annotations=[])
    @staticmethod
    def interrupt() -> "Cause[E]": return Cause(kind='interrupt', annotations=[])
    @staticmethod
    def both(l: "Cause[E]", r: "Cause[E]") -> "Cause[E]": return Cause(kind='both', left=l, right=r, annotations=[])
    @staticmethod
    def then(l: "Cause[E]", r: "Cause[E]") -> "Cause[E]": return Cause(kind='then', left=l, right=r, annotations=[])

def annotate_cause(c: Cause[E], note: str) -> Cause[E]:
    notes = list(c.annotations or []); notes.append(note)
    return Cause(kind=c.kind, left=c.left, right=c.right, error=c.error, defect=c.defect, annotations=notes)

class Context: ...

class Effect(Generic[R, E, A]):
    def __init__(self, run: Callable[[Context], Awaitable[A]]): self._run_impl = run
    async def _run(self, ctx: "Context") -> A: return await self._run_impl(ctx)

    def map(self, f: Callable[[A], B]) -> "Effect[R, E, B]":
        async def run(ctx: Context): return f(await self._run(ctx))
        return Effect(run)

    def flat_map(self, f: Callable[[A], "Effect[R, E, B]"]) -> "Effect[R, E, B]":
        async def run(ctx: Context): a = await self._run(ctx); return await f(a)._run(ctx)
        return Effect(run)

    def catch_all(self, f: Callable[[E], "Effect[R, E2, A]"]) -> "Effect[R, E2, A]":
        async def run(ctx: Context):
            try: return await self._run(ctx)
            except Failure as fe: return await f(fe.error)._run(ctx)
        return Effect(run)

    def provide(self, layer: _LayerLike) -> "Effect[Any, E, A]":
        async def run(ctx: Context):
            sub = await layer.build(ctx)
            try: return await self._run(sub)
            finally: await layer.teardown(sub)
        return Effect(run)

    # Provide a layer using a fresh Scope and ensure teardown via scope closure
    def provide_scoped(self, layer: Any) -> "Effect[Any, E, A]":
        async def run(ctx: Context):
            scope = Scope()
            sub = await layer.build_scoped(ctx, scope)  # type: ignore[attr-defined]
            try:
                return await self._run(sub)
            finally:
                await scope.close()
        return Effect(run)

    # New: sequential zip combining results as a tuple
    def zip(self, other: "Effect[R, E, B]") -> "Effect[R, E, Tuple[A, B]]":
        async def run(ctx: Context):
            a = await self._run(ctx)
            b = await other._run(ctx)
            return (a, b)
        return Effect(run)

    # New: sequential zipWith
    def zip_with(self, other: "Effect[R, E, B]", f: Callable[[A, B], B]) -> "Effect[R, E, B]":
        async def run(ctx: Context):
            a = await self._run(ctx)
            b = await other._run(ctx)
            return f(a, b)
        return Effect(run)

    # New: fold both failure and success into a value
    def fold(self, on_error: Callable[[E], B], on_success: Callable[[A], B]) -> "Effect[R, Any, B]":
        async def run(ctx: Context):
            try:
                a = await self._run(ctx)
                return on_success(a)
            except Failure as fe:
                return on_error(fe.error)
        return Effect(run)

    # New: fold into Effects (aka matchEffect)
    def fold_effect(self, on_error: Callable[[E], "Effect[R, E2, B]"], on_success: Callable[[A], "Effect[R, E2, B]"]) -> "Effect[R, E2, B]":
        async def run(ctx: Context):
            try:
                a = await self._run(ctx)
                return await on_success(a)._run(ctx)
            except Failure as fe:
                return await on_error(fe.error)._run(ctx)
        return Effect(run)

    # Alias for fold_effect
    def match_effect(self, on_error: Callable[[E], "Effect[R, E2, B]"], on_success: Callable[[A], "Effect[R, E2, B]"]) -> "Effect[R, E2, B]":
        return self.fold_effect(on_error, on_success)

    # New: ensure finalizer runs after this effect (ignore finalizer failures)
    def ensuring(self, finalizer: "Effect[Any, Any, Any]") -> "Effect[R, E, A]":
        async def run(ctx: Context):
            try:
                return await self._run(ctx)
            finally:
                try:
                    await finalizer._run(ctx)
                except Exception:
                    # Swallow finalizer errors to preserve original outcome
                    pass
        return Effect(run)

    # New: timeout returning Optional[A]; None when timed out
    def timeout(self, seconds: float) -> "Effect[R, Any, Optional[A]]":
        async def run(ctx: Context):
            try:
                return await asyncio.wait_for(self._run(ctx), timeout=seconds)
            except asyncio.TimeoutError:
                return None
        return Effect(run)

    # Annotate failures in this effect with a note (propagates to Cause in fibers)
    def annotate(self, note: str) -> "Effect[R, E, A]":
        async def run(ctx: Context):
            try:
                return await self._run(ctx)
            except Failure as fe:
                ann = list(getattr(fe, 'annotations', []))
                ann.append(note)
                raise Failure(fe.error, annotations=ann)
        return Effect(run)

    # New: map Failure error type
    def map_error(self, f: Callable[[E], E2]) -> "Effect[R, E2, A]":
        async def run(ctx: Context):
            try:
                return await self._run(ctx)
            except Failure as fe:
                raise Failure(f(fe.error))
        return Effect(run)

    # New: refine error or die (convert to defect)
    def refine_or_die(self, pf: Callable[[E], Optional[E2]]) -> "Effect[R, E2, A]":
        async def run(ctx: Context):
            try:
                return await self._run(ctx)
            except Failure as fe:
                new = pf(fe.error)
                if new is None:
                    # Convert to defect by raising a non-Failure
                    raise RuntimeError(f"Unrefined error: {fe.error!r}")
                raise Failure(new)
        return Effect(run)

    # New: run side-effecting effect on error, then re-raise
    def on_error(self, side: Callable[[E], "Effect[Any, Any, None]"]) -> "Effect[R, E, A]":
        async def run(ctx: Context):
            try:
                return await self._run(ctx)
            except Failure as fe:
                try:
                    await side(fe.error)._run(ctx)
                finally:
                    # Re-raise original failure
                    raise
        return Effect(run)

    # New: run side-effecting effect on interrupt, then re-raise cancellation
    def on_interrupt(self, side: "Effect[Any, Any, None]") -> "Effect[R, E, A]":
        async def run(ctx: Context):
            try:
                return await self._run(ctx)
            except asyncio.CancelledError:
                try:
                    await side._run(ctx)
                finally:
                    raise
        return Effect(run)

    # Retry failures according to a Schedule; dies propagate
    def retry(self, schedule: Schedule) -> "Effect[R, E, A]":  # type: ignore[type-var]
        async def run(ctx: Context):
            schedule.reset()
            while True:
                try:
                    return await self._run(ctx)
                except Failure as fe:
                    cont, delay, _ = schedule.step(fe.error)  # type: ignore[arg-type]
                    if not cont:
                        raise
                    if delay > 0:
                        await asyncio.sleep(delay)
                    # loop
        return Effect(run)

    # Repeat successes according to a Schedule
    def repeat(self, schedule: Schedule) -> "Effect[R, E, A]":  # type: ignore[type-var]
        async def run(ctx: Context):
            schedule.reset()
            last: Optional[A] = None
            while True:
                last = await self._run(ctx)
                cont, delay, _ = schedule.step(last)  # type: ignore[arg-type]
                if not cont:
                    return last
                if delay > 0:
                    await asyncio.sleep(delay)
        return Effect(run)

def succeed(a: A) -> Effect[Any, Any, A]:
    async def run(_: Context): return a
    return Effect(run)

def fail(e: E) -> Effect[Any, E, Any]:
    async def run(_: Context): raise Failure(e)
    return Effect(run)

def from_async(thunk: Callable[[], Awaitable[A]]) -> Effect[Any, Any, A]:
    async def run(_: Context): return await thunk()
    return Effect(run)

# Run an effect built with a Scope, guaranteeing scope closure
def scoped(f: Callable[[Scope], Effect[Any, E, A]]) -> Effect[Any, E, A]:
    async def run(ctx: Context):
        scope = Scope()
        try:
            eff = f(scope)
            if asyncio.iscoroutine(eff):  # support async factory returning Effect
                eff = await eff  # type: ignore[assignment]
            return await eff._run(ctx)
        finally:
            await scope.close()
    return Effect(run)

def sync(thunk: Callable[[], A]) -> Effect[Any, Any, A]:
    async def run(_: Context): return thunk()
    return Effect(run)

def attempt(thunk: Callable[[], A], on_error: Callable[[BaseException], E]) -> Effect[Any, E, A]:
    async def run(_: Context):
        try: return thunk()
        except BaseException as ex: raise Failure(on_error(ex))
    return Effect(run)

def uninterruptible(eff: Effect[R, E, A]) -> Effect[R, E, A]:
    async def run(ctx: Context):
        async def worker(): return await eff._run(ctx)
        task = asyncio.create_task(worker())
        try: return await task
        except asyncio.CancelledError:
            try: return await task
            finally: raise
    return Effect(run)

def uninterruptibleMask(f: Callable[[Callable[[Effect[R,E,A]], Effect[R,E,A]]], Effect[R,E,A]]) -> Effect[R,E,A]:
    async def run(ctx: Context):
        async def restore(inner: Effect[R,E,A]) -> Effect[R,E,A]:
            async def r(ctx2: Context):
                t = asyncio.create_task(inner._run(ctx2)); return await t
            return Effect(r)
        return await uninterruptible(f(restore))._run(ctx)
    return Effect(run)

# Resource safety: acquire/release semantics (aka bracket)
def acquire_release(acquire: Effect[Any, E, A], release: Callable[[A], Effect[Any, Any, Any]], use: Callable[[A], Effect[Any, E2, B]]) -> Effect[Any, E | E2, B]:
    async def run(ctx: Context):
        # Use uninterruptible mask to acquire/release safely, restore around use
        async def inner(_: Context):
            a = await acquire._run(ctx)
            async def body(ctx2: Context):
                try:
                    return await use(a)._run(ctx2)
                finally:
                    try:
                        await release(a)._run(ctx2)
                    except Exception:
                        # Release errors are swallowed to preserve original cause
                        pass
            return await body(ctx)
        return await Effect(inner)._run(ctx)
    return Effect(run)

# Parallel zip: runs both effects concurrently, cancels the other on failure
def zip_par(e1: Effect[Any, E, A], e2: Effect[Any, E, B]) -> Effect[Any, E, Tuple[A, B]]:
    async def run(ctx: Context):
        async def r1(): return await e1._run(ctx)
        async def r2(): return await e2._run(ctx)
        t1 = asyncio.create_task(r1())
        t2 = asyncio.create_task(r2())
        try:
            a = await t1
            b = await t2
            return (a, b)
        except BaseException:
            # Cancel whichever is still pending
            if not t1.done(): t1.cancel()
            if not t2.done(): t2.cancel()
            # Drain tasks
            for t in (t1, t2):
                try:
                    await t
                except BaseException:
                    pass
            raise
    return Effect(run)

# Race: returns the first to complete (success or failure), cancels the other
def race(e1: Effect[Any, E, A], e2: Effect[Any, E, A]) -> Effect[Any, E, A]:
    async def run(ctx: Context):
        async def r1(): return await e1._run(ctx)
        async def r2(): return await e2._run(ctx)
        t1 = asyncio.create_task(r1())
        t2 = asyncio.create_task(r2())
        done, pending = await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
        first = next(iter(done))
        # Cancel the other
        for p in pending: p.cancel()
        try:
            res = await first
            return res
        finally:
            # Drain the pending task
            for p in pending:
                try:
                    await p
                except BaseException:
                    pass
    return Effect(run)

# for_each_par: run f over items with bounded concurrency, preserving order
T = TypeVar("T")
def for_each_par(items: Iterable[T], f: Callable[[T], Effect[Any, E, A]], parallelism: int = 10) -> Effect[Any, E, List[A]]:
    async def run(ctx: Context):
        sem = asyncio.Semaphore(max(1, parallelism))
        seq = list(items)
        results: List[Optional[A]] = [None] * len(seq)

        async def worker(i: int, x: T):
            async with sem:
                results[i] = await f(x)._run(ctx)

        tasks = [asyncio.create_task(worker(i, x)) for i, x in enumerate(seq)]
        try:
            # Wait for tasks; cancel pending on first exception
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION)
            # Check if any done task raised
            for t in done:
                exc = t.exception()
                if exc is not None:
                    # Cancel all pending and drain
                    for p in pending:
                        p.cancel()
                    for p in pending:
                        try:
                            await p
                        except BaseException:
                            pass
                    raise exc
            # If no exceptions yet, await remaining
            await asyncio.gather(*pending)
        except BaseException:
            # Propagate after ensuring all tasks cleaned
            raise
        return [r for r in results if r is not None]
    return Effect(run)

# Race across many effects: return first result, cancel rest
def race_first(effects: Iterable[Effect[Any, E, A]]) -> Effect[Any, E, A]:
    async def run(ctx: Context):
        tasks = [asyncio.create_task(eff._run(ctx)) for eff in effects]
        if not tasks:
            # No effects to race
            raise RuntimeError("race_first on empty iterable")
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        winner = next(iter(done))
        # Cancel others
        for p in pending:
            p.cancel()
        try:
            result = await winner
            return result
        finally:
            # Drain pending tasks
            for p in pending:
                try:
                    await p
                except BaseException:
                    pass
    return Effect(run)

# Race across many effects: return (index, result) of first; cancel rest
def race_all(effects: Iterable[Effect[Any, E, A]]) -> Effect[Any, E, Tuple[int, A]]:
    async def run(ctx: Context):
        effs = list(effects)
        tasks = [asyncio.create_task(e._run(ctx)) for e in effs]
        if not tasks:
            raise RuntimeError("race_all on empty iterable")
        index_map = {t: i for i, t in enumerate(tasks)}
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        winner = next(iter(done))
        for p in pending:
            p.cancel()
        try:
            val = await winner
            return (index_map[winner], val)
        finally:
            for p in pending:
                try:
                    await p
                except BaseException:
                    pass
    return Effect(run)

# Merge many effects with optional parallelism, collect results
def merge_all(effects: Iterable[Effect[Any, E, A]], parallelism: Optional[int] = None, preserve_order: bool = False) -> Effect[Any, E, List[A]]:
    async def run(ctx: Context):
        eff_iter = iter(effects)
        results: List[A] = []
        if parallelism is None or parallelism <= 0:
            # Unbounded: start all
            tasks = [asyncio.create_task(e._run(ctx)) for e in eff_iter]
        else:
            # Bounded: start up to parallelism
            tasks: List[asyncio.Task] = []
            for _ in range(parallelism):
                try:
                    e = next(eff_iter)
                except StopIteration:
                    break
                tasks.append(asyncio.create_task(e._run(ctx)))
        # If preserving order, just gather
        if preserve_order:
            try:
                vals = await asyncio.gather(*tasks)
                results.extend(vals)
            except BaseException:
                # Cancel remaining
                for t in tasks:
                    if not t.done():
                        t.cancel()
                for t in tasks:
                    try:
                        await t
                    except BaseException:
                        pass
                raise
            # Drain rest of iterator sequentially if any
            for e in eff_iter:
                results.append(await e._run(ctx))
            return results
        # Unordered: collect in completion order and maintain bounded pool
        try:
            while tasks:
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                # Get results of all completed tasks
                for d in done:
                    # Propagate exception immediately after cancelling pending
                    exc = None
                    try:
                        v = await d
                        results.append(v)
                    except BaseException as ex:
                        exc = ex
                    if exc is not None:
                        # Cancel pending and drain
                        for p in pending:
                            p.cancel()
                        for p in pending:
                            try:
                                await p
                            except BaseException:
                                pass
                        raise exc
                # Refill tasks from iterator
                tasks = list(pending)
                if parallelism is not None and parallelism > 0:
                    to_add = parallelism - len(tasks)
                    for _ in range(to_add):
                        try:
                            e = next(eff_iter)
                        except StopIteration:
                            break
                        tasks.append(asyncio.create_task(e._run(ctx)))
            # If iterator still has effects and no parallelism limit, add them (unlikely due to above handling)
            for e in eff_iter:
                results.append(await e._run(ctx))
            return results
        except BaseException:
            raise
    return Effect(run)
