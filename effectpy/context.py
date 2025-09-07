from __future__ import annotations
from typing import Any, Dict, TypeVar

A = TypeVar("A")

class Context:
    def __init__(self, values: Dict[type, Any] | None = None): self._values = dict(values or {})
    def get(self, t: type[A]) -> A:
        if t not in self._values: raise KeyError(f"Missing service: {t}")
        return self._values[t]
    def add(self, t: type[A], v: A) -> "Context":
        c = dict(self._values); c[t] = v; return Context(c)
