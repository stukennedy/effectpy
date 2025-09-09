import asyncio
import io
import json
import sys
import unittest
from contextlib import redirect_stderr

from effectpy import Context, Scope
from effectpy.logger import ConsoleLogger, LoggerLayer
from effectpy.tracer import TracerLayer, Tracer
from effectpy.metrics import MetricsLayer
from effectpy.instrument import instrument
from effectpy.core import Effect


class TestObservability(unittest.IsolatedAsyncioTestCase):
    async def test_logger_includes_trace_ids_and_json(self):
        base = Context(); scope = Scope()
        env = await (LoggerLayer | TracerLayer).build_scoped(base, scope)
        logger = env.get(ConsoleLogger)
        logger.json_output = True
        buf = io.StringIO()

        async def work(_):
            return 1

        eff = instrument("obs.test", Effect(work))
        with redirect_stderr(buf):
            await eff._run(env)
        s = buf.getvalue().strip().splitlines()
        self.assertTrue(len(s) >= 2)
        rec = json.loads(s[0])
        self.assertIn("trace_id", rec)
        self.assertIn("span_id", rec)

        await scope.close()

    async def test_metrics_labels(self):
        base = Context(); scope = Scope()
        env = await (MetricsLayer).build_scoped(base, scope)
        reg = env.get(type(env.get)) if False else env.get  # quiet type
        from effectpy.metrics import MetricsRegistry
        m = env.get(MetricsRegistry)
        c = await m.counter("requests_total", labels=(("route", "/foo"), ("method", "GET")))
        c.inc(2)
        key = [k for k in m.counters.keys() if k.startswith("requests_total|")][0]
        self.assertEqual(m.counters[key].value, 2)
        await scope.close()

    async def test_tracer_attributes_events_links(self):
        base = Context(); scope = Scope()
        env = await (TracerLayer).build_scoped(base, scope)
        tr = env.get(Tracer)
        sp = await tr.start_span("attr.test")
        await tr.add_attribute(sp, "k", "v")
        await tr.add_event(sp, "evt", {"a": 1})
        await tr.add_link(sp, sp.trace_id, sp.span_id, {"l": True})
        await tr.end_span(sp, status="OK")

        last = tr.export[-1]
        self.assertEqual(last.attributes.get("k"), "v")
        self.assertTrue(last.events and last.events[0][0] == "evt")
        self.assertTrue(last.links and last.links[0][0] == sp.trace_id)
        await scope.close()

