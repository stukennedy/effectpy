from __future__ import annotations
from typing import Awaitable, Callable, Any
from .context import Context
from .scope import Scope

class Layer:
    def __init__(self, acquire: Callable[[Context, dict], Awaitable[Context]], release: Callable[[Context, dict], Awaitable[None]]):
        self._acquire = acquire; self._release = release

    async def build(self, parent: Context) -> Context: return await self._acquire(parent, {})
    async def build_memo(self, parent: Context, memo: dict) -> Context: return await self._acquire(parent, memo)

    async def build_scoped(self, parent: Context, scope: Scope, memo: dict | None = None) -> Context:
        memo = memo or {}
        ctx = await self._acquire(parent, memo)
        async def fin(): await self._release(ctx, memo)
        await scope.add_finalizer(fin)
        return ctx

    async def teardown(self, ctx: Context) -> None: await self._release(ctx, {})
    async def teardown_memo(self, ctx: Context, memo: dict) -> None: await self._release(ctx, memo)

    def __add__(self, other: "Layer") -> "Layer":
        async def acq(parent: Context, memo: dict):
            left = await self.build_memo(parent, memo); right = await other.build_memo(left, memo); return right
        async def rel(ctx: Context, memo: dict):
            await other.teardown_memo(ctx, memo); await self.teardown_memo(ctx, memo)
        return Layer(acq, rel)

    def __or__(self, other: "Layer") -> "Layer":
        import asyncio
        async def acq(parent: Context, memo: dict):
            c1, c2 = await asyncio.gather(self.build_memo(parent, memo), other.build_memo(parent, memo))
            merged = c1
            for k, v in c2._values.items():
                merged = merged.add(k, v)
            return merged
        async def rel(ctx: Context, memo: dict):
            import asyncio; await asyncio.gather(self.teardown_memo(ctx, memo), other.teardown_memo(ctx, memo))
        return Layer(acq, rel)

def from_resource(t: type, mk: Callable[[Context], Awaitable[Any]], close: Callable[[Any], Awaitable[None]]) -> Layer:
    async def acquire(parent: Context, memo: dict):
        key = ('resource', t)
        if key in memo: inst = memo[key]
        else:
            inst = await mk(parent); memo[key] = inst
        return parent.add(t, inst)
    async def release(ctx: Context, memo: dict):
        key = ('resource', t)
        inst = memo.get(key) or ctx.get(t)
        await close(inst)
    return Layer(acquire, release)
