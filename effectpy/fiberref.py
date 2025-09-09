from __future__ import annotations
import contextvars
from typing import Generic, TypeVar

from .core import Effect
from .context import Context

T = TypeVar("T")


class FiberRef(Generic[T]):
    def __init__(self, initial: T):
        # Each FiberRef has its own ContextVar, inherited to child tasks
        self._initial = initial
        self._var: contextvars.ContextVar[T] = contextvars.ContextVar(
            f"fiberref_{id(self)}", default=initial
        )

    def get(self) -> Effect[object, object, T]:
        async def run(_ctx: Context) -> T:
            return self._var.get()

        return Effect(run)

    def set(self, value: T) -> Effect[object, object, None]:
        async def run(_ctx: Context) -> None:
            self._var.set(value)
            return None

        return Effect(run)

    def locally(self, value: T, eff: Effect) -> Effect:
        async def run(ctx: Context):
            token = self._var.set(value)
            try:
                return await eff._run(ctx)
            finally:
                self._var.reset(token)

        return Effect(run)

