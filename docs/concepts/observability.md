# Observability

`instrument(name, eff, tags=...)` captures logs, metrics, traces.

- Logger: structured JSON or plain text with levels and correlation ids
- Metrics: counters/gauges/histograms (with labels)
- Tracer: spans with attributes/events/links; simple OTLP exporters

Exporters use `aiohttp` when installed; otherwise no-op.

