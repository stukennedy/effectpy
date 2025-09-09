import asyncio
import unittest

from effectpy import Context
from effectpy.stream import StreamE, sink_head, sink_drain


class TestStreamExtras(unittest.IsolatedAsyncioTestCase):
    async def test_map_buffer_collect(self):
        s = StreamE.from_iterable([1, 2, 3]).map(lambda x: x * 2).buffer(4)
        from effectpy.stream import sink_fold

        total = await s.run(sink_fold(0, lambda acc, x: acc + x))._run(Context())
        self.assertEqual(total, 12)

    async def test_sink_head_and_drain(self):
        s = StreamE.from_iterable([10, 20, 30])
        h = await s.run(sink_head())._run(Context())
        self.assertEqual(h, 10)

        await s.run(sink_drain())._run(Context())
        # drain completes without error

