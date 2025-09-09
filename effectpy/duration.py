from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class Duration:
    seconds: float

    @staticmethod
    def seconds_(s: float) -> "Duration":
        return Duration(float(s))

    @staticmethod
    def millis(ms: float) -> "Duration":
        return Duration(float(ms) / 1000.0)

    @staticmethod
    def minutes(m: float) -> "Duration":
        return Duration(float(m) * 60.0)

    def __add__(self, other: "Duration") -> "Duration":
        return Duration(self.seconds + other.seconds)

    def __mul__(self, k: float) -> "Duration":
        return Duration(self.seconds * float(k))

    def __str__(self) -> str:
        s = self.seconds
        if s < 1.0:
            return f"{int(s*1000)}ms"
        if s < 60.0:
            return f"{s:.3f}s"
        m = int(s // 60)
        rem = s - m * 60
        return f"{m}m{rem:.3f}s"

