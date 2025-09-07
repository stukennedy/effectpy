import unittest
import asyncio

from effectpy.context import Context
from effectpy.scope import Scope
from effectpy.instrument import instrument
from effectpy.core import Effect
from effectpy.logger import LoggerLayer
from effectpy.metrics import MetricsLayer, MetricsRegistry
from effectpy.tracer import TracerLayer, Tracer


class TestInstrument(unittest.IsolatedAsyncioTestCase):
    async def test_instrument_records_span_and_histogram(self):
        # Compose env with logger, metrics, tracer
        base = Context()
        scope = Scope()
        env = await (LoggerLayer | MetricsLayer | TracerLayer).build_scoped(base, scope)

        async def work(_):
            await asyncio.sleep(0.01)
            return 123

        eff = Effect(work)
        name = "unit.test"
        tags = {"component": "t", "env": "ci"}
        wrapped = instrument(name, eff, tags=tags)
        v = await wrapped._run(env)
        self.assertEqual(v, 123)

        # Check tracer got a span
        tracer = env.get(Tracer)
        self.assertTrue(len(tracer.export) >= 1)
        self.assertIn(name, tracer.export[-1].name)

        # Check metrics histogram recorded
        metrics = env.get(MetricsRegistry)
        # name is effect_duration_seconds_<name>_component=...,env=...
        key_prefix = f"effect_duration_seconds_{name}"
        keys = [k for k in metrics.hists.keys() if k.startswith(key_prefix)]
        self.assertTrue(keys, "histogram not recorded")
        h = metrics.hists[keys[0]]
        self.assertGreaterEqual(h.count, 1)

        await scope.close()

