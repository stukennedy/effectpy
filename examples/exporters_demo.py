"""
Exporters Demo: send spans and metrics over OTLP HTTP (mock payload).

Notes:
- Requires `aiohttp` to actually send; otherwise the exporter functions no-op.
- Endpoints below match OpenTelemetry Collector defaults; adjust as needed.

Run: python examples/exporters_demo.py
"""
import asyncio

from effectpy import (
    Effect,
    Context,
    Scope,
    instrument,
    LoggerLayer,
    MetricsLayer,
    TracerLayer,
)
from effectpy import exporters as exp


async def compute(_):
    await asyncio.sleep(0.01)
    return 42


async def main():
    base = Context()
    scope = Scope()
    env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(base, scope)

    eff = instrument("export.demo", Effect(compute), tags={"service": "demo"})
    val = await eff._run(env)
    print("value =>", val)

    # Import the services by type and fetch from the environment
    from effectpy.tracer import Tracer
    from effectpy.metrics import MetricsRegistry
    tracer = env.get(Tracer)
    metrics = env.get(MetricsRegistry)

    # Export spans and metrics; if aiohttp is missing, exporters do nothing
    if getattr(exp, "aiohttp", None) is None:
        print("aiohttp not installed; skipping actual HTTP export.")
    else:
        spans_endpoint = "http://localhost:4318/v1/traces"
        metrics_endpoint = "http://localhost:4318/v1/metrics"
        print(f"exporting to {spans_endpoint} and {metrics_endpoint} ...")
        try:
            await exp.export_spans_otlp_http(tracer, spans_endpoint)
            await exp.export_metrics_otlp_http(metrics, metrics_endpoint)
            print("exports completed.")
        except Exception as ex:
            print(f"export failed or blocked: {ex}")

    await scope.close()


if __name__ == "__main__":
    asyncio.run(main())
