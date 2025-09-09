import asyncio
import unittest

from effectpy import Effect, Context, Schedule, fail, Failure, succeed


class TestRetryRepeat(unittest.IsolatedAsyncioTestCase):
    async def test_retry_recurs_succeeds_eventually(self):
        attempts = {"n": 0}

        async def sometimes_fails(_):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise Failure("boom")
            return 42

        eff = Effect(sometimes_fails)
        sch = Schedule.recurs(5)
        v = await eff.retry(sch)._run(Context())
        self.assertEqual(v, 42)
        self.assertEqual(attempts["n"], 3)

    async def test_retry_exhausts_and_raises(self):
        attempts = {"n": 0}

        async def always_fail(_):
            attempts["n"] += 1
            raise Failure("nope")

        eff = Effect(always_fail)
        sch = Schedule.recurs(2)
        with self.assertRaises(Failure):
            await eff.retry(sch)._run(Context())
        # 1 initial + 2 retries = 3 total attempts
        self.assertEqual(attempts["n"], 3)

    async def test_retry_with_delay(self):
        attempts = {"n": 0}

        async def fail_then_succeed(_):
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise Failure("x")
            return 7

        eff = Effect(fail_then_succeed)
        sch = Schedule.exponential(0.001, max_delay=0.002)
        v = await eff.retry(sch)._run(Context())
        self.assertEqual(v, 7)
        self.assertEqual(attempts["n"], 2)

    async def test_repeat_recurs_runs_n_plus_one_times(self):
        runs = {"n": 0}

        async def tick(_):
            runs["n"] += 1
            await asyncio.sleep(0)
            return runs["n"]

        eff = Effect(tick)
        sch = Schedule.recurs(2)  # run initial + 2 repeats
        last = await eff.repeat(sch)._run(Context())
        self.assertEqual(last, 3)
        self.assertEqual(runs["n"], 3)

