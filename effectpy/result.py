from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

E = TypeVar("E")
A = TypeVar("A")
B = TypeVar("B")


class Result(Generic[E, A]):
    def is_ok(self) -> bool: raise NotImplementedError
    def is_err(self) -> bool: return not self.is_ok()

    def map(self, f: Callable[[A], B]) -> "Result[E, B]":
        if self.is_ok():
            return Ok(f(self.value))  # type: ignore[attr-defined]
        return self  # type: ignore[return-value]

    def map_err(self, f: Callable[[E], B]) -> "Result[B, A]":
        if self.is_err():
            return Err(f(self.error))  # type: ignore[attr-defined]
        return Ok(self.value)  # type: ignore[attr-defined]

    def and_then(self, f: Callable[[A], "Result[E, B]"]) -> "Result[E, B]":
        if self.is_ok():
            return f(self.value)  # type: ignore[attr-defined]
        return self  # type: ignore[return-value]

    def get_or_else(self, default: A) -> A:
        return self.value if self.is_ok() else default  # type: ignore[attr-defined]


@dataclass(frozen=True)
class Ok(Result[E, A]):
    value: A
    def is_ok(self) -> bool: return True


@dataclass(frozen=True)
class Err(Result[E, A]):
    error: E
    def is_ok(self) -> bool: return False


def from_either(e: "Either[E, A]") -> Result[E, A]:
    from .either import Left, Right
    if isinstance(e, Left):
        return Err(e.error)
    else:
        return Ok(e.value)  # type: ignore[attr-defined]


def to_either(r: Result[E, A]) -> "Either[E, A]":
    from .either import Left, Right
    if isinstance(r, Err):
        return Left(r.error)
    else:
        return Right(r.value)  # type: ignore[attr-defined]

