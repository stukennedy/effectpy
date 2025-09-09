import asyncio
import unittest

from effectpy import Context
from effectpy.stream import Stream, stream_stage


class TestStream(unittest.IsolatedAsyncioTestCase):
    async def test_stream_from_iterable_map_collect(self):
        async def inc(x: int) -> int:
            await asyncio.sleep(0.001)
            return x + 1

        async def square(x: int) -> int:
            await asyncio.sleep(0.001)
            return x * x

        s = (
            Stream.from_iterable(range(5))
            .via(stream_stage(inc, workers=2, out_capacity=2))
            .via(stream_stage(square, workers=2, out_capacity=2))
        )

        out = await s.run_collect()._run(Context())
        # Order is preserved per stage in this simple design; validate values regardless of order
        self.assertEqual(sorted(out), sorted([(i + 1) * (i + 1) for i in range(5)]))

    async def test_stream_empty(self):
        s = Stream.from_iterable([])
        out = await s.run_collect()._run(Context())
        self.assertEqual(out, [])

