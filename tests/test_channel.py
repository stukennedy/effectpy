import asyncio
import unittest

from effectpy.channel import Channel


class TestChannel(unittest.IsolatedAsyncioTestCase):
    async def test_send_receive(self):
        ch: Channel[int] = Channel(maxsize=1)
        await ch.send(5)
        v = await ch.receive()
        self.assertEqual(v, 5)

    async def test_send_on_closed_raises(self):
        ch: Channel[int] = Channel()
        await ch.close()
        with self.assertRaises(RuntimeError):
            await ch.send(1)

