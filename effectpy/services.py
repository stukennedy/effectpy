from __future__ import annotations
from typing import Any, Tuple, TypeVar

from .core import Effect, Failure
from .context import Context
from .layer import Layer

A = TypeVar("A")
B = TypeVar("B")
C = TypeVar("C")


def service(t: type[A]) -> Effect[object, KeyError, A]:
    async def run(ctx: Context) -> A:
        try:
            return ctx.get(t)
        except KeyError as e:
            # Map missing service into Failure(KeyError)
            raise Failure(e)

    return Effect(run)


def services(t1: type[A], t2: type[B]) -> Effect[object, KeyError, Tuple[A, B]]:
    async def run(ctx: Context) -> Tuple[A, B]:
        try:
            return (ctx.get(t1), ctx.get(t2))
        except KeyError as e:
            raise Failure(e)

    return Effect(run)


def provide_service(t: type[A], value: A) -> Layer:
    async def acquire(parent: Context, _memo: dict) -> Context:
        return parent.add(t, value)

    async def release(_ctx: Context, _memo: dict) -> None:
        return None

    return Layer(acquire, release)

