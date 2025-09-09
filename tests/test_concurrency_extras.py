import asyncio
import unittest

from effectpy import (
    Effect,
    Context,
    succeed,
    fail,
    for_each_par,
    race_first,
    race_all,
    merge_all,
)


class TestConcurrencyExtras(unittest.IsolatedAsyncioTestCase):
    async def test_race_first_multiple(self):
        async def slow(v, t):
            await asyncio.sleep(t)
            return v
        effs = [Effect(lambda _, v=i, t=0.02 + 0.01 * i: slow(v, t)) for i in range(3)]
        # Inject a fast one
        effs.insert(1, Effect(lambda _: slow(99, 0.005)))
        v = await race_first(effs)._run(Context())
        self.assertEqual(v, 99)

    async def test_race_all_returns_index(self):
        async def slow(v, t):
            await asyncio.sleep(t)
            return v
        effs = [Effect(lambda _, v=i, t=0.02 + 0.01 * i: slow(v, t)) for i in range(3)]
        idx, v = await race_all(effs)._run(Context())
        self.assertEqual(v, 0)
        self.assertEqual(idx, 0)

    async def test_merge_all_unordered(self):
        async def slow(v, t):
            await asyncio.sleep(t)
            return v
        effs = [Effect(lambda _, v=i: slow(v, 0.02 - 0.001 * i)) for i in range(10)]
        vals = await merge_all(effs)._run(Context())
        self.assertEqual(sorted(vals), list(range(10)))

    async def test_merge_all_bounded(self):
        async def slow(v, t):
            await asyncio.sleep(t)
            return v
        effs = [Effect(lambda _, v=i: slow(v, 0.01)) for i in range(5)]
        vals = await merge_all(effs, parallelism=2)._run(Context())
        self.assertEqual(sorted(vals), list(range(5)))

    async def test_for_each_par_cancels_on_failure(self):
        done = {"count": 0}

        async def work(x: int, _):
            if x == 0:
                raise Exception("boom")
            await asyncio.sleep(0.05)
            done["count"] += 1
            return x

        with self.assertRaises(Exception):
            await for_each_par([0, 1, 2, 3], lambda x: Effect(lambda ctx: work(x, ctx)), parallelism=4)._run(Context())
        # Ensure not all others completed due to cancellation
        self.assertLess(done["count"], 3)

