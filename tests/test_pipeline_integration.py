import asyncio
import unittest

from effectpy import Pipeline, stage
from effectpy.channel import Channel
from effectpy.context import Context


class TestPipelineIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_pipeline_via_stream_to_channel(self):
        src: Channel[int] = Channel(maxsize=10)
        out: Channel[int] = Channel(maxsize=10)

        async def inc(x: int) -> int:
            await asyncio.sleep(0.001)
            return x + 1

        async def square(x: int) -> int:
            await asyncio.sleep(0.001)
            return x * x

        pipe = (
            Pipeline[int, int](src)
            .via(stage(inc, workers=2, out_capacity=4))
            .via(stage(square, workers=2, out_capacity=4))
        )

        # Start pipeline in background
        await pipe.to_channel(out)._run(Context())

        N = 6
        async def producer():
            for i in range(N):
                await src.send(i)

        async def consumer():
            results = []
            for _ in range(N):
                v = await out.receive()
                results.append(v)
            return results

        results = await asyncio.gather(producer(), consumer())
        vals = results[1]
        # (i+1)^2 for i in 0..N-1
        self.assertEqual(vals, [(i + 1) * (i + 1) for i in range(N)])

