import asyncio
import unittest

from effectpy import Context
from effectpy.stream import Stream


class TestStreamMore(unittest.IsolatedAsyncioTestCase):
    async def test_map_and_fold(self):
        s = Stream.from_iterable([1, 2, 3, 4]).map(lambda x: x * 2)
        total = await s.run_fold(0, lambda acc, x: acc + x)._run(Context())
        self.assertEqual(total, 20)

    async def test_merge(self):
        left = Stream.from_iterable([1, 3, 5])
        right = Stream.from_iterable([2, 4, 6])
        merged = left.merge(right)
        out = await merged.run_collect()._run(Context())
        self.assertEqual(sorted(out), [1, 2, 3, 4, 5, 6])

    async def test_buffer_identity(self):
        # Buffer doesn't change values
        s = Stream.from_iterable(list(range(10))).buffer(4)
        out = await s.run_collect()._run(Context())
        self.assertEqual(out, list(range(10)))

