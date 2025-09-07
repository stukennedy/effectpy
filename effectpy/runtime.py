from __future__ import annotations
import asyncio
from typing import Optional, TypeVar, Any, Generic
from .context import Context
from .core import Failure, Exit, Cause, Effect
from .scope import Scope

E = TypeVar("E"); A = TypeVar("A")

class Fiber(Generic[E, A]):
    def __init__(self, task: asyncio.Task): self._task = task
    async def await_(self) -> Exit[E, A]:
        try: v = await self._task; return Exit(success=True, value=v)
        except Failure as fe: return Exit(success=False, cause=Cause.fail(fe.error))
        except asyncio.CancelledError: return Exit(success=False, cause=Cause.interrupt())
        except BaseException as ex: return Exit(success=False, cause=Cause.die(ex))
    def interrupt(self) -> None: self._task.cancel()

class Runtime:
    def __init__(self, base: Optional[Context] = None): self.base = base or Context()
    def fork(self, eff: Effect[Any, E, A]) -> Fiber[E, A]:
        async def runner(): return await eff._run(self.base)
        return Fiber(asyncio.create_task(runner()))
    async def run(self, eff: Effect[Any, E, A]) -> A: return await eff._run(self.base)
    async def run_scoped(self, eff: Effect[Any, E, A], scope: Scope) -> A:
        try: return await eff._run(self.base)
        finally: await scope.close()
