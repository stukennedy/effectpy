from __future__ import annotations
try:
    import aiohttp
except Exception:
    aiohttp = None
from .tracer import Tracer
from .metrics import MetricsRegistry, Counter, Gauge, Histogram

async def export_spans_otlp_http(tracer: Tracer, endpoint: str) -> None:
    if aiohttp is None: return
    # Very rough OTLP-like payload; not spec compliant but structured
    def span_to_dict(s):
        return {
            "traceId": s.trace_id,
            "spanId": s.span_id,
            "parentSpanId": s.parent_id,
            "name": s.name,
            "start": s.start,
            "end": s.end,
            "status": s.status,
            "error": s.error,
            "attributes": s.attributes,
            "events": [{"name": n, "time": t, "attributes": a} for (n,t,a) in getattr(s, 'events', [])],
            "links": [{"traceId": ti, "spanId": si, "attributes": a} for (ti,si,a) in getattr(s, 'links', [])],
        }
    payload = {"resourceSpans": [span_to_dict(s) for s in tracer.export]}
    async with aiohttp.ClientSession() as sess:
        async with sess.post(endpoint, json=payload) as resp:
            await resp.read()

async def export_metrics_otlp_http(metrics: MetricsRegistry, endpoint: str) -> None:
    if aiohttp is None: return
    counters = [{"name": v.name, "labels": dict(getattr(v, 'labels', ())), "value": v.value} for v in metrics.counters.values()] if hasattr(metrics, 'counters') else []
    gauges = [{"name": v.name, "labels": dict(getattr(v, 'labels', ())), "value": v.value} for v in metrics.gauges.values()] if hasattr(metrics, 'gauges') else []
    hists = [{"name": h.name, "labels": dict(getattr(h, 'labels', ())), "sum": h.sum, "count": h.count, "buckets": h.buckets, "counts": h.counts} for h in metrics.hists.values()] if hasattr(metrics, 'hists') else []
    payload = {"counters": counters, "gauges": gauges, "histograms": hists}
    async with aiohttp.ClientSession() as sess:
        async with sess.post(endpoint, json=payload) as resp:
            await resp.read()
