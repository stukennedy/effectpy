from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

E = TypeVar("E")
A = TypeVar("A")
B = TypeVar("B")


class Either(Generic[E, A]):
    def is_left(self) -> bool: raise NotImplementedError
    def is_right(self) -> bool: return not self.is_left()

    def map(self, f: Callable[[A], B]) -> "Either[E, B]":
        if self.is_right():
            return Right(f(self.value))  # type: ignore[attr-defined]
        return self  # type: ignore[return-value]

    def flat_map(self, f: Callable[[A], "Either[E, B]"]) -> "Either[E, B]":
        if self.is_right():
            return f(self.value)  # type: ignore[attr-defined]
        return self  # type: ignore[return-value]

    def map_left(self, f: Callable[[E], B]) -> "Either[B, A]":
        if self.is_left():
            return Left(f(self.error))  # type: ignore[attr-defined]
        return Right(self.value)  # type: ignore[attr-defined]

    def get_or_else(self, default: A) -> A:
        return self.value if self.is_right() else default  # type: ignore[attr-defined]


@dataclass(frozen=True)
class Left(Either[E, A]):
    error: E
    def is_left(self) -> bool: return True


@dataclass(frozen=True)
class Right(Either[E, A]):
    value: A
    def is_left(self) -> bool: return False

