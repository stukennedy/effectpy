import asyncio
import unittest

from effectpy import Context
from effectpy import succeed
from effectpy.stream import StreamE, Sink, sink_fold
from effectpy.core import Effect


class TestStreamErrorAndSink(unittest.IsolatedAsyncioTestCase):
    async def test_map_effect_and_fold(self):
        # map_effect that succeeds, then fold
        s = StreamE.from_iterable([1, 2, 3])

        def f(x: int):
            return succeed(x + 1)

        s2 = s.via_effect(f)
        total = await s2.run(sink_fold(0, lambda acc, x: acc + x))._run(Context())
        self.assertEqual(total, 9)

    async def test_filter_take(self):
        s = StreamE.from_iterable(range(10)).filter(lambda x: x % 2 == 0).take(3)
        out = await s.run(sink_fold([], lambda acc, x: acc + [x]))._run(Context())
        self.assertEqual(out, [0, 2, 4])

    async def test_timeout_errors(self):
        # Source that sleeps before emitting its first value
        def delayed_source():
            def build(out, err):
                async def run(_):
                    await asyncio.sleep(0.05)
                    await out.send(1)
                    await out.close()
                    return None
                return Effect(run)
            return StreamE(build)

        s = delayed_source().timeout(0.01)
        with self.assertRaises(asyncio.TimeoutError):
            await s.run(sink_fold(0, lambda acc, x: acc + x))._run(Context())
