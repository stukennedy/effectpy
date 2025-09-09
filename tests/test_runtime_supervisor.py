import asyncio
import unittest

from effectpy.runtime import Runtime, Supervisor
from effectpy.core import Effect, fail, Failure
from effectpy.context import Context


class RecordingSupervisor(Supervisor):
    def __init__(self):
        self.events: list[tuple[str, str]] = []

    async def on_start(self, fiber):
        self.events.append(("start", fiber.id))

    async def on_end(self, fiber, exit_):
        self.events.append(("end", fiber.id))

    async def on_failure(self, fiber, cause):
        self.events.append(("fail", fiber.id))


class TestRuntimeSupervisor(unittest.IsolatedAsyncioTestCase):
    async def test_fiber_metadata_and_join(self):
        rt = Runtime(Context())

        async def work(_):
            await asyncio.sleep(0.01)
            return 7

        f = rt.fork(Effect(work), name="w1")
        self.assertEqual(f.status, "running")
        v = await f.join()
        self.assertEqual(v, 7)
        self.assertEqual(f.status, "done")
        self.assertTrue(isinstance(f.id, str) and len(f.id) > 0)
        self.assertEqual(f.name, "w1")

    async def test_supervisor_receives_events(self):
        sup = RecordingSupervisor()
        rt = Runtime(Context(), supervisor=sup)

        good = Effect(lambda _: _async_const(1))
        bad = fail("nope")

        f1 = rt.fork(good, name="good")
        f2 = rt.fork(bad, name="bad")
        # Wait for fibers to finish
        await asyncio.gather(f1.await_(), f2.await_())

        kinds = [k for k, _ in sup.events]
        self.assertIn("start", kinds)
        self.assertIn("end", kinds)
        self.assertIn("fail", kinds)


async def _async_const(x):
    await asyncio.sleep(0)
    return x

