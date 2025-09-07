from __future__ import annotations
from typing import Optional, TypeVar, Generic, Any, Callable, Awaitable
import anyio
from .context import Context
from .core import Failure, Exit, Cause, Effect
from .scope import Scope

E = TypeVar('E'); A = TypeVar('A')

class AnyIOFiber(Generic[E, A]):
    def __init__(self, done_event: anyio.Event, get_result: Callable[[], tuple[bool, Any, Any]], cancel_scope: anyio.CancelScope):
        self._done = done_event; self._get_result = get_result; self._scope = cancel_scope
    async def await_(self) -> Exit[E, A]:
        await self._done.wait()
        ok, value, err = self._get_result()
        if ok: return Exit(success=True, value=value)
        import anyio as _a
        if isinstance(err, Failure): return Exit(success=False, cause=Cause.fail(err.error))
        if isinstance(err, _a.get_cancelled_exc_class()): return Exit(success=False, cause=Cause.interrupt())
        return Exit(success=False, cause=Cause.die(err))
    def interrupt(self) -> None: self._scope.cancel()

class AnyIORuntime:
    def __init__(self, base: Optional[Context] = None): self.base = base or Context(); self._tg: Optional[anyio.abc.TaskGroup] = None
    async def __aenter__(self) -> 'AnyIORuntime': self._tg = await anyio.create_task_group().__aenter__(); return self
    async def __aexit__(self, et, e, tb): assert self._tg is not None; await self._tg.__aexit__(et, e, tb); self._tg=None
    async def run(self, eff: Effect[Any, E, A]) -> A:
        async def _m(): return await eff._run(self.base)
        return await _m()
    async def run_scoped(self, eff: Effect[Any, E, A], scope: Scope) -> A:
        try: return await eff._run(self.base)
        finally: await scope.close()
    async def fork(self, eff: Effect[Any, E, A]) -> AnyIOFiber[E, A]:
        if self._tg is None: raise RuntimeError("Use AnyIORuntime in 'async with' context")
        done = anyio.Event(); result: dict[str, Any] = {}
        async def worker(task_status=anyio.TASK_STATUS_IGNORED):
            with anyio.CancelScope() as scope:
                task_status.started(scope)
                try: v = await eff._run(self.base); result.update(ok=True, value=v, err=None)
                except BaseException as ex: result.update(ok=False, value=None, err=ex)
                finally: done.set()
        scope = await self._tg.start(worker)  # type: ignore
        def _get(): return (bool(result.get('ok', False)), result.get('value'), result.get('err'))
        return AnyIOFiber(done, _get, scope)
