from __future__ import annotations
import random as _rand
from typing import Iterable, Sequence, TypeVar

from .layer import from_resource, Layer
from .context import Context

T = TypeVar("T")


class Random:
    def __init__(self, rng: _rand.Random | None = None) -> None:
        self._rng = rng or _rand.Random()

    async def next_float(self) -> float:
        return self._rng.random()

    async def next_int(self, bound: int) -> int:
        if bound <= 0:
            raise ValueError("bound must be > 0")
        return self._rng.randrange(bound)

    async def choice(self, seq: Sequence[T]) -> T:
        if not seq:
            raise ValueError("empty sequence")
        return self._rng.choice(seq)


async def _mk_random(_ctx: Context) -> Random:
    return Random()


async def _close_random(_r: Random) -> None:
    return None


RandomLayer = from_resource(Random, _mk_random, _close_random)


def TestRandomLayer(seed: int) -> Layer:
    async def mk(_ctx: Context) -> Random:
        return Random(_rand.Random(seed))

    async def close(_r: Random) -> None:
        return None

    return from_resource(Random, mk, close)


# Effect helpers
from .core import Effect


def random_int(bound: int) -> Effect[object, object, int]:
    async def run(ctx: Context) -> int:
        rnd = ctx.get(Random)
        return await rnd.next_int(bound)

    return Effect(run)


def random_float() -> Effect[object, object, float]:
    async def run(ctx: Context) -> float:
        rnd = ctx.get(Random)
        return await rnd.next_float()

    return Effect(run)

