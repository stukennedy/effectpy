from __future__ import annotations
from dataclasses import dataclass
from typing import Awaitable, Callable, Generic, TypeVar, Any, Optional, Protocol, runtime_checkable
import asyncio

R = TypeVar("R"); E = TypeVar("E"); A = TypeVar("A"); B = TypeVar("B"); E2 = TypeVar("E2")

@dataclass
class Exit(Generic[E, A]):
    success: bool
    value: Optional[A] = None
    cause: Optional["Cause[E]"] = None

class Failure(Exception, Generic[E]):
    def __init__(self, error: E):
        super().__init__(repr(error)); self.error = error

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

def succeed(a: A) -> Effect[Any, Any, A]:
    async def run(_: Context): return a
    return Effect(run)

def fail(e: E) -> Effect[Any, E, Any]:
    async def run(_: Context): raise Failure(e)
    return Effect(run)

def from_async(thunk: Callable[[], Awaitable[A]]) -> Effect[Any, Any, A]:
    async def run(_: Context): return await thunk()
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
