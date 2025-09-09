import asyncio
import unittest

from effectpy import Deferred, Ref, Queue, QueueClosed


class TestDeferred(unittest.IsolatedAsyncioTestCase):
    async def test_deferred_succeed(self):
        d: Deferred[int] = Deferred()
        async def waiter():
            return await d.await_()
        task = asyncio.create_task(waiter())
        await asyncio.sleep(0)
        d.succeed(5)
        v = await task
        self.assertEqual(v, 5)

    async def test_deferred_fail(self):
        d: Deferred[int] = Deferred()
        async def waiter():
            return await d.await_()
        task = asyncio.create_task(waiter())
        await asyncio.sleep(0)
        d.fail(ValueError("boom"))
        with self.assertRaises(ValueError):
            await task


class TestRef(unittest.IsolatedAsyncioTestCase):
    async def test_ref_get_set_update_modify(self):
        r: Ref[int] = Ref(1)
        self.assertEqual(await r.get(), 1)
        await r.set(2)
        self.assertEqual(await r.get(), 2)
        await r.update(lambda x: x + 3)
        self.assertEqual(await r.get(), 5)
        out = await r.modify(lambda x: (x * 10, x - 1))
        self.assertEqual(out, 50)
        self.assertEqual(await r.get(), 4)


class TestQueue(unittest.IsolatedAsyncioTestCase):
    async def test_queue_send_receive(self):
        q: Queue[int] = Queue(maxsize=1)
        await q.send(1)
        v = await q.receive()
        self.assertEqual(v, 1)

    async def test_queue_close_behavior(self):
        q: Queue[int] = Queue()
        await q.send(1)
        await q.close()
        # Can drain remaining item
        v = await q.receive()
        self.assertEqual(v, 1)
        # Then closed and empty => raises
        with self.assertRaises(QueueClosed):
            await q.receive()
        with self.assertRaises(QueueClosed):
            await q.send(2)

