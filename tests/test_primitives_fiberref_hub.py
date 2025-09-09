import asyncio
import unittest

from effectpy import FiberRef, Hub, HubClosed
from effectpy.core import Effect
from effectpy.context import Context
from effectpy.runtime import Runtime


class TestFiberRef(unittest.IsolatedAsyncioTestCase):
    async def test_get_set_locally(self):
        ref = FiberRef[int](0)

        v0 = await ref.get()._run(Context())
        self.assertEqual(v0, 0)

        await ref.set(5)._run(Context())
        v1 = await ref.get()._run(Context())
        self.assertEqual(v1, 5)

        async def read(_):
            return await ref.get()._run(Context())

        eff = Effect(read)
        v2 = await ref.locally(9, eff)._run(Context())
        self.assertEqual(v2, 9)

        # after locally, value restored
        v3 = await ref.get()._run(Context())
        self.assertEqual(v3, 5)

    async def test_inheritance_on_fork(self):
        ref = FiberRef[str]("root")
        await ref.set("parent")._run(Context())

        async def read(_):
            return await ref.get()._run(Context())

        eff = Effect(read)
        rt = Runtime(Context())
        f = rt.fork(eff)
        ex = await f.await_()
        self.assertTrue(ex.success)
        self.assertEqual(ex.value, "parent")


class TestHub(unittest.IsolatedAsyncioTestCase):
    async def test_publish_subscribe(self):
        hub: Hub[int] = Hub()
        sub1 = await hub.subscribe(maxsize=10)
        sub2 = await hub.subscribe(maxsize=10)

        await hub.publish(1)
        await hub.publish(2)

        self.assertEqual(await sub1.receive(), 1)
        self.assertEqual(await sub2.receive(), 1)
        self.assertEqual(await sub1.receive(), 2)
        self.assertEqual(await sub2.receive(), 2)

        await sub1.close()
        await hub.publish(3)
        self.assertEqual(await sub2.receive(), 3)

        await hub.close()
        with self.assertRaises(HubClosed):
            await hub.publish(4)

        # sub2 should drain and then raise on receive
        with self.assertRaises(Exception):
            # Our Queue raises QueueClosed, but we just assert it raises
            await sub2.receive()
