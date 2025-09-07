import asyncio
import unittest

from effectpy.runtime import Runtime
from effectpy.core import Effect, fail, Failure
from effectpy.context import Context


class TestRuntime(unittest.IsolatedAsyncioTestCase):
    async def test_run_success(self):
        eff = Effect(lambda _: _async_const(7))
        rt = Runtime(Context())
        v = await rt.run(eff)
        self.assertEqual(v, 7)

    async def test_fiber_success_and_await(self):
        eff = Effect(lambda _: _async_const(1))
        rt = Runtime(Context())
        fiber = rt.fork(eff)
        exit_ = await fiber.await_()
        self.assertTrue(exit_.success)
        self.assertEqual(exit_.value, 1)

    async def test_fiber_failure_maps_to_cause_fail(self):
        eff = fail("nope")
        rt = Runtime(Context())
        fiber = rt.fork(eff)
        ex = await fiber.await_()
        self.assertFalse(ex.success)
        self.assertEqual(ex.cause.kind, "fail")
        self.assertEqual(ex.cause.error, "nope")

    async def test_fiber_interrupt(self):
        async def slow(_: Context):
            await asyncio.sleep(1)
        eff = Effect(slow)
        rt = Runtime(Context())
        fiber = rt.fork(eff)
        fiber.interrupt()
        ex = await fiber.await_()
        self.assertFalse(ex.success)
        self.assertEqual(ex.cause.kind, "interrupt")


async def _async_const(x):
    await asyncio.sleep(0)
    return x

