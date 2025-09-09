import asyncio
import unittest

from effectpy import Context
from effectpy.core import Effect
from effectpy.stream import StreamE, sink_fold


class TestStreamResource(unittest.IsolatedAsyncioTestCase):
    async def test_via_acquire_release_per_worker(self):
        events: list[str] = []

        async def acquire(_):
            events.append("acq")
            return object()

        async def release(obj):
            events.append("rel")

        async def work(r, x: int, _):
            await asyncio.sleep(0.001)
            return x * 2

        src = StreamE.from_iterable([1, 2, 3, 4])

        eff_acq = Effect(acquire)
        def rel_e(r):
            return Effect(lambda _: release(r))
        def fn(r, x):
            return Effect(lambda ctx: work(r, x, ctx))

        s2 = src.via_acquire_release(eff_acq, rel_e, fn, workers=2, out_capacity=2)
        total = await s2.run(sink_fold(0, lambda acc, v: acc + v))._run(Context())
        self.assertEqual(total, 20)
        # Two workers acquire and release
        self.assertEqual(events.count("acq"), 2)
        self.assertEqual(events.count("rel"), 2)

