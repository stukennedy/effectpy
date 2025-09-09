import asyncio
import time
import unittest

from effectpy import (
    Context,
    Scope,
    Clock,
    ClockLayer,
    TestClockLayer,
    sleep,
    current_time,
    Random,
    RandomLayer,
    TestRandomLayer,
    random_int,
    random_float,
)


class TestClockServices(unittest.IsolatedAsyncioTestCase):
    async def test_clock_sleep_advances_time(self):
        base = Context()
        scope = Scope()
        env = await ClockLayer.build_scoped(base, scope)

        t0 = await current_time()._run(env)
        await sleep(0.01)._run(env)
        t1 = await current_time()._run(env)
        self.assertGreaterEqual(t1 - t0, 0.009)
        await scope.close()

    async def test_testclock_sleep_is_instant_and_advances_now(self):
        base = Context()
        scope = Scope()
        env = await TestClockLayer(start=100.0).build_scoped(base, scope)

        wall0 = time.monotonic()
        t0 = await current_time()._run(env)
        await sleep(1.23)._run(env)
        t1 = await current_time()._run(env)
        wall1 = time.monotonic()

        # Immediate (no real wait)
        self.assertLess(wall1 - wall0, 0.05)
        # Logical time advanced by 1.23
        self.assertAlmostEqual(t1 - t0, 1.23, places=6)
        await scope.close()


class TestRandomServices(unittest.IsolatedAsyncioTestCase):
    async def test_random_reproducibility_with_seed(self):
        base1 = Context(); scope1 = Scope()
        env1 = await TestRandomLayer(123).build_scoped(base1, scope1)
        a1 = await random_int(1000)._run(env1)
        b1 = await random_float()._run(env1)

        base2 = Context(); scope2 = Scope()
        env2 = await TestRandomLayer(123).build_scoped(base2, scope2)
        a2 = await random_int(1000)._run(env2)
        b2 = await random_float()._run(env2)

        self.assertEqual(a1, a2)
        self.assertEqual(b1, b2)

        await scope1.close(); await scope2.close()

