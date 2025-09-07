from __future__ import annotations
try:
    import aiohttp
except Exception:
    aiohttp = None
from .tracer import Tracer
from .metrics import MetricsRegistry

async def export_spans_otlp_http(tracer: Tracer, endpoint: str) -> None:
    if aiohttp is None: return
    payload = {"resourceSpans": [vars(s) for s in tracer.export]}
    async with aiohttp.ClientSession() as sess:
        async with sess.post(endpoint, json=payload) as resp:
            await resp.read()

async def export_metrics_otlp_http(metrics: MetricsRegistry, endpoint: str) -> None:
    if aiohttp is None: return
    counters = [{"name": k, "value": v.value} for k,v in metrics.counters.items()] if hasattr(metrics, 'counters') else []
    gauges = [{"name": k, "value": v.value} for k,v in metrics.gauges.items()] if hasattr(metrics, 'gauges') else []
    hists = [{"name": k, "sum": h.sum, "count": h.count, "buckets": h.buckets, "counts": h.counts} for k,h in metrics.hists.items()] if hasattr(metrics, 'hists') else []
    payload = {"counters": counters, "gauges": gauges, "histograms": hists}
    async with aiohttp.ClientSession() as sess:
        async with sess.post(endpoint, json=payload) as resp:
            await resp.read()
