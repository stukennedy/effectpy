from __future__ import annotations
import time, uuid, contextvars
from dataclasses import dataclass
from typing import Optional
from .layer import from_resource
from .context import Context

_trace_id = contextvars.ContextVar('trace_id', default=None)
_span_id = contextvars.ContextVar('span_id', default=None)

@dataclass
class Span:
    trace_id: str; span_id: str; parent_id: Optional[str]; name: str; start: float; end: Optional[float]=None; status: str="OK"; error: Optional[str]=None

class Tracer:
    def __init__(self): self.export: list[Span] = []
    async def start_span(self, name: str) -> Span:
        trace_id = _trace_id.get() or uuid.uuid4().hex; parent = _span_id.get(); span_id = uuid.uuid4().hex
        _trace_id.set(trace_id); _span_id.set(span_id)
        sp = Span(trace_id=trace_id, span_id=span_id, parent_id=parent, name=name, start=time.time())
        self.export.append(sp); return sp
    async def end_span(self, span: Span, status: str="OK", error: Optional[str]=None) -> None:
        span.end = time.time(); span.status=status; span.error=error; _span_id.set(span.parent_id)

async def _mk(_ctx: Context) -> Tracer: return Tracer()
async def _close(_t: Tracer) -> None: return None
TracerLayer = from_resource(Tracer, _mk, _close)
