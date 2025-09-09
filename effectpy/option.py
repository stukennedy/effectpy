from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Generic, Optional, TypeVar

T = TypeVar("T")
U = TypeVar("U")


class Option(Generic[T]):
    def is_some(self) -> bool: raise NotImplementedError
    def is_none(self) -> bool: return not self.is_some()

    def map(self, f: Callable[[T], U]) -> "Option[U]":
        if self.is_some():
            return Some(f(self.value))  # type: ignore[attr-defined]
        return NONE

    def flat_map(self, f: Callable[[T], "Option[U]"]) -> "Option[U]":
        if self.is_some():
            return f(self.value)  # type: ignore[attr-defined]
        return NONE

    def get_or_else(self, default: U) -> T | U:
        return self.value if self.is_some() else default  # type: ignore[attr-defined]


@dataclass(frozen=True)
class Some(Option[T]):
    value: T
    def is_some(self) -> bool: return True


class _None(Option[None]):
    __slots__ = ()
    def __repr__(self) -> str: return "None"
    def is_some(self) -> bool: return False


NONE: Option[None] = _None()


def from_nullable(v: Optional[T]) -> Option[T]:
    return Some(v) if v is not None else NONE  # type: ignore[return-value]

