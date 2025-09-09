from __future__ import annotations
import time, uuid, contextvars
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple
from .layer import from_resource
from .context import Context

_trace_id = contextvars.ContextVar('trace_id', default=None)
_span_id = contextvars.ContextVar('span_id', default=None)

@dataclass
class Span:
    trace_id: str
    span_id: str
    parent_id: Optional[str]
    name: str
    start: float
    end: Optional[float] = None
    status: str = "OK"
    error: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Tuple[str, float, Dict[str, Any]]] = field(default_factory=list)
    links: List[Tuple[str, str, Dict[str, Any]]] = field(default_factory=list)  # (trace_id, span_id, attrs)

class Tracer:
    def __init__(self): self.export: list[Span] = []
    async def start_span(self, name: str) -> Span:
        trace_id = _trace_id.get() or uuid.uuid4().hex; parent = _span_id.get(); span_id = uuid.uuid4().hex
        _trace_id.set(trace_id); _span_id.set(span_id)
        sp = Span(trace_id=trace_id, span_id=span_id, parent_id=parent, name=name, start=time.time())
        self.export.append(sp); return sp
    async def end_span(self, span: Span, status: str="OK", error: Optional[str]=None) -> None:
        span.end = time.time(); span.status=status; span.error=error; _span_id.set(span.parent_id)

    async def add_attribute(self, span: Span, key: str, value: Any) -> None:
        span.attributes[key] = value

    async def add_event(self, span: Span, name: str, attrs: Optional[Dict[str, Any]] = None) -> None:
        span.events.append((name, time.time(), dict(attrs or {})))

    async def add_link(self, span: Span, trace_id: str, span_id: str, attrs: Optional[Dict[str, Any]] = None) -> None:
        span.links.append((trace_id, span_id, dict(attrs or {})))

def current_trace_id() -> Optional[str]:
    return _trace_id.get()

def current_span_id() -> Optional[str]:
    return _span_id.get()

async def _mk(_ctx: Context) -> Tracer: return Tracer()
async def _close(_t: Tracer) -> None: return None
TracerLayer = from_resource(Tracer, _mk, _close)
