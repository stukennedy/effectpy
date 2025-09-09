from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Generic, Iterable, Iterator, List, Sequence, Tuple, TypeVar

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True)
class Chunk(Generic[T]):
    _items: Tuple[T, ...]

    @staticmethod
    def of(*items: T) -> "Chunk[T]":
        return Chunk(tuple(items))

    @staticmethod
    def from_iterable(items: Iterable[T]) -> "Chunk[T]":
        return Chunk(tuple(items))

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def to_list(self) -> List[T]:
        return list(self._items)

    def map(self, f: Callable[[T], U]) -> "Chunk[U]":
        return Chunk(tuple(f(x) for x in self._items))

    def flat_map(self, f: Callable[[T], "Chunk[U]"]) -> "Chunk[U]":
        out: List[U] = []
        for x in self._items:
            out.extend(f(x)._items)
        return Chunk(tuple(out))

    def filter(self, p: Callable[[T], bool]) -> "Chunk[T]":
        return Chunk(tuple(x for x in self._items if p(x)))

    def append(self, x: T) -> "Chunk[T]":
        return Chunk(self._items + (x,))

    def extend(self, xs: Iterable[T]) -> "Chunk[T]":
        return Chunk(self._items + tuple(xs))

    def __len__(self) -> int:
        return len(self._items)

