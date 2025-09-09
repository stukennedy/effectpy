from __future__ import annotations
import random
from dataclasses import dataclass
from typing import Callable, Generic, Optional, Tuple, TypeVar

S = TypeVar("S"); In = TypeVar("In"); Out = TypeVar("Out")


@dataclass
class Step(Generic[S, Out]):
    # continue_: if True, effect should run again after `delay`
    continue_: bool
    delay: float
    out: Out
    state: S


class Schedule(Generic[S, In, Out]):
    def __init__(self, initial: S, step_fn: Callable[[S, In], Step[S, Out]]):
        self._state = initial
        self._initial = initial
        self._step_fn = step_fn

    def reset(self) -> None:
        self._state = self._initial

    def step(self, inp: In) -> Tuple[bool, float, Out]:
        s = self._step_fn(self._state, inp)
        self._state = s.state
        return (s.continue_, s.delay, s.out)

    # Factories
    @staticmethod
    def recurs(n: int) -> "Schedule[int, In, int]":
        # Repeat up to n times (i.e., allow n more runs after the first)
        def step_fn(state: int, _inp: In) -> Step[int, int]:
            if state <= 0:
                return Step(continue_=False, delay=0.0, out=0, state=state)
            return Step(continue_=True, delay=0.0, out=state, state=state - 1)

        return Schedule(initial=n, step_fn=step_fn)

    @staticmethod
    def spaced(interval: float) -> "Schedule[int, In, int]":
        def step_fn(state: int, _inp: In) -> Step[int, int]:
            # Always continue; caller decides when to stop by composing
            return Step(continue_=True, delay=max(0.0, interval), out=state, state=state + 1)

        return Schedule(initial=0, step_fn=step_fn)

    @staticmethod
    def exponential(base: float, max_delay: Optional[float] = None) -> "Schedule[int, In, float]":
        def step_fn(state: int, _inp: In) -> Step[int, float]:
            delay = base * (2 ** max(0, state))
            if max_delay is not None:
                delay = min(delay, max_delay)
            return Step(continue_=True, delay=delay, out=delay, state=state + 1)

        return Schedule(initial=0, step_fn=step_fn)

    def jittered(self, min_factor: float = 0.5, max_factor: float = 1.5) -> "Schedule[S, In, Out]":
        base_step = self._step_fn

        def step_fn(state: S, inp: In) -> Step[S, Out]:
            s = base_step(state, inp)
            factor = random.uniform(min_factor, max_factor)
            return Step(continue_=s.continue_, delay=max(0.0, s.delay * factor), out=s.out, state=s.state)

        return Schedule(initial=self._state, step_fn=step_fn)

