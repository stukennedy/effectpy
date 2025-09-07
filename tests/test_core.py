import asyncio
import unittest

from effectpy.core import Effect, succeed, fail, Failure, attempt, sync
from effectpy.context import Context


class TestCoreEffect(unittest.IsolatedAsyncioTestCase):
    async def test_succeed_map_flatmap(self):
        eff = succeed(2).map(lambda x: x + 3).flat_map(lambda y: succeed(y * 2))
        v = await eff._run(Context())
        self.assertEqual(v, 10)

    async def test_fail_and_catch_all(self):
        eff = fail("boom").catch_all(lambda e: succeed(f"handled:{e}"))
        v = await eff._run(Context())
        self.assertEqual(v, "handled:boom")

    async def test_attempt_maps_exception_to_failure(self):
        def bad():
            raise ValueError("bad")

        eff = attempt(bad, lambda ex: f"err:{type(ex).__name__}")
        with self.assertRaises(Failure) as cm:
            await eff._run(Context())
        self.assertEqual(cm.exception.error, "err:ValueError")

    # Note: uninterruptible semantics are tricky; covered as improvement area.
