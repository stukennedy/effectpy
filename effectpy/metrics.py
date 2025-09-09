from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Iterable, Tuple
import asyncio
from .layer import from_resource
from .context import Context

@dataclass
class Counter:
    name: str
    help: str = ""
    labels: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    value: int = 0
def _c_inc(self, n:int=1): self.value += n
Counter.inc = _c_inc  # type: ignore

@dataclass
class Gauge:
    name: str
    help: str = ""
    labels: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    value: float = 0.0
def _g_set(self,v:float): self.value=v
def _g_inc(self,v:float=1.0): self.value+=v
def _g_dec(self,v:float=1.0): self.value-=v
Gauge.set=_g_set; Gauge.inc=_g_inc; Gauge.dec=_g_dec  # type: ignore

@dataclass
class Histogram:
    name: str; help: str = ""; buckets: List[float] = field(default_factory=lambda:[0.005,0.01,0.025,0.05,0.1,0.25,0.5,1.0,2.5,5.0,10.0])
    labels: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    counts: List[int] = field(init=False); sum: float = 0.0; count: int = 0
    def __post_init__(self): self.counts = [0 for _ in self.buckets] + [0]
    def observe(self, v: float) -> None:
        self.sum += v; self.count += 1; placed=False
        for i,b in enumerate(self.buckets):
            if v <= b: self.counts[i]+=1; placed=True; break
        if not placed: self.counts[-1]+=1

class MetricsRegistry:
    def __init__(self):
        self.counters: Dict[str, Counter]={}
        self.gauges: Dict[str, Gauge]={}
        self.hists: Dict[str, Histogram]={}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(name: str, labels: Iterable[Tuple[str, str]] | None) -> str:
        if not labels:
            return name
        return name + "|" + ",".join([f"{k}={v}" for k,v in sorted(labels)])

    async def counter(self, name: str, help: str = "", labels: Iterable[Tuple[str,str]]|None=None) -> Counter:
        async with self._lock:
            key = self._key(name, labels)
            c = self.counters.get(key)
            if c is None:
                c = Counter(name, help, tuple(sorted(labels or [])))
                self.counters[key] = c
            return c

    async def gauge(self, name: str, help: str = "", labels: Iterable[Tuple[str,str]]|None=None) -> Gauge:
        async with self._lock:
            key = self._key(name, labels)
            g = self.gauges.get(key)
            if g is None:
                g = Gauge(name, help, tuple(sorted(labels or [])))
                self.gauges[key] = g
            return g

    async def histogram(self, name:str, help:str="", buckets:Iterable[float]|None=None)->Histogram:
        async with self._lock:
            base = Histogram(name='tmp')
            h=self.hists.get(name) or Histogram(name,help, list(buckets) if buckets else base.buckets)  # type: ignore
            self.hists[name]=h; return h

    async def histogram_labeled(self, name:str, help:str="", labels: Iterable[Tuple[str,str]]|None=None, buckets:Iterable[float]|None=None)->Histogram:
        async with self._lock:
            key = self._key(name, labels)
            base = Histogram(name='tmp')
            h=self.hists.get(key) or Histogram(name,help, list(buckets) if buckets else base.buckets, tuple(sorted(labels or [])))  # type: ignore
            self.hists[key]=h; return h

async def _mk(_ctx: Context) -> MetricsRegistry: return MetricsRegistry()
async def _close(_m: MetricsRegistry) -> None: return None
MetricsLayer = from_resource(MetricsRegistry, _mk, _close)
