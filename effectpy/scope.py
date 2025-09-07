from __future__ import annotations
from typing import Awaitable, Callable, List

class Scope:
    def __init__(self):
        self._finalizers: List[Callable[[], Awaitable[None]]] = []
        self._closed = False

    async def add_finalizer(self, fin: Callable[[], Awaitable[None]]) -> None:
        if self._closed: await fin()
        else: self._finalizers.append(fin)

    async def close(self) -> None:
        if self._closed: return
        self._closed = True
        while self._finalizers:
            fin = self._finalizers.pop()
            try: await fin()
            except Exception: pass
