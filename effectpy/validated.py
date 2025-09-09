from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Generic, Iterable, List, Tuple, TypeVar

E = TypeVar("E")
A = TypeVar("A")
B = TypeVar("B")


class Validated(Generic[E, A]):
    def is_valid(self) -> bool: raise NotImplementedError
    def is_invalid(self) -> bool: return not self.is_valid()

    def map(self, f: Callable[[A], B]) -> "Validated[E, B]":
        if self.is_valid():
            return Valid(f(self.value))  # type: ignore[attr-defined]
        return self  # type: ignore[return-value]

    def ap(self, vf: "Validated[E, Callable[[A], B]]") -> "Validated[E, B]":
        # Applicative apply that accumulates errors
        if self.is_valid() and vf.is_valid():
            return Valid(vf.value(self.value))  # type: ignore[attr-defined]
        errs: List[E] = []
        if self.is_invalid():
            errs.extend(self.errors)  # type: ignore[attr-defined]
        if vf.is_invalid():
            errs.extend(vf.errors)  # type: ignore[attr-defined]
        return Invalid(errs)

    def combine(self, other: "Validated[E, B]") -> "Validated[E, Tuple[A, B]]":
        if self.is_valid() and other.is_valid():
            return Valid((self.value, other.value))  # type: ignore[attr-defined]
        errs: List[E] = []
        if self.is_invalid():
            errs.extend(self.errors)  # type: ignore[attr-defined]
        if other.is_invalid():
            errs.extend(other.errors)  # type: ignore[attr-defined]
        return Invalid(errs)


@dataclass(frozen=True)
class Valid(Validated[E, A]):
    value: A
    def is_valid(self) -> bool: return True


@dataclass(frozen=True)
class Invalid(Validated[E, A]):
    errors: List[E]
    def is_valid(self) -> bool: return False


def map2(a: Validated[E, A], b: Validated[E, B], f: Callable[[A, B], B]) -> Validated[E, B]:
    if a.is_valid() and b.is_valid():
        return Valid(f(a.value, b.value))  # type: ignore[attr-defined]
    errs: List[E] = []
    if a.is_invalid():
        errs.extend(a.errors)  # type: ignore[attr-defined]
    if b.is_invalid():
        errs.extend(b.errors)  # type: ignore[attr-defined]
    return Invalid(errs)

