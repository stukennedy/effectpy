import asyncio
import unittest

from effectpy import (
    Effect,
    succeed,
    fail,
    attempt,
    Context,
    acquire_release,
    zip_par,
    race,
    for_each_par,
)


class TestCoreCombinators(unittest.IsolatedAsyncioTestCase):
    async def test_zip_sequential(self):
        eff = succeed(1).zip(succeed(2))
        v = await eff._run(Context())
        self.assertEqual(v, (1, 2))

    async def test_fold_success_and_failure(self):
        ok = succeed(3).fold(lambda e: f"L:{e}", lambda a: f"R:{a}")
        v1 = await ok._run(Context())
        self.assertEqual(v1, "R:3")

        bad = fail("oops").fold(lambda e: f"L:{e}", lambda a: f"R:{a}")
        v2 = await bad._run(Context())
        self.assertEqual(v2, "L:oops")

    async def test_ensuring_runs_on_success_and_failure(self):
        box = {"n": 0}

        async def inc(_):
            box["n"] += 1

        finalizer = Effect(inc)

        ok = succeed(1).ensuring(finalizer)
        v = await ok._run(Context())
        self.assertEqual(v, 1)
        self.assertEqual(box["n"], 1)

        async def boom(_):
            raise Exception("kaboom")

        with self.assertRaises(Exception):
            await Effect(boom).ensuring(finalizer)._run(Context())
        self.assertEqual(box["n"], 2)

    async def test_acquire_release(self):
        events: list[str] = []

        async def mk(_):
            events.append("acquire")
            return 10

        async def rel(x: int):
            events.append(f"release:{x}")

        async def use_ok(x: int, _):
            return x * 2

        eff_ok = acquire_release(Effect(mk), lambda x: Effect(lambda _: rel(x)), lambda x: Effect(lambda ctx: use_ok(x, ctx)))
        v = await eff_ok._run(Context())
        self.assertEqual(v, 20)

        async def use_fail(x: int, _):
            raise Exception("fail")

        eff_bad = acquire_release(Effect(mk), lambda x: Effect(lambda _: rel(x)), lambda x: Effect(lambda ctx: use_fail(x, ctx)))
        with self.assertRaises(Exception):
            await eff_bad._run(Context())

        # Two acquires and two releases total
        self.assertEqual(events, ["acquire", "release:10", "acquire", "release:10"])

    async def test_timeout(self):
        async def slow(_):
            await asyncio.sleep(0.05)
            return 42

        res_none = await Effect(slow).timeout(0.001)._run(Context())
        self.assertIsNone(res_none)

        res_val = await Effect(slow).timeout(0.5)._run(Context())
        self.assertEqual(res_val, 42)


class TestConcurrencyCombinators(unittest.IsolatedAsyncioTestCase):
    async def test_zip_par(self):
        async def a(_):
            await asyncio.sleep(0.02)
            return 1

        async def b(_):
            await asyncio.sleep(0.03)
            return 2

        v = await zip_par(Effect(a), Effect(b))._run(Context())
        self.assertEqual(v, (1, 2))

    async def test_race(self):
        async def fast(_):
            await asyncio.sleep(0.01)
            return "fast"

        async def slow(_):
            await asyncio.sleep(0.05)
            return "slow"

        r = await race(Effect(fast), Effect(slow))._run(Context())
        self.assertEqual(r, "fast")

    async def test_for_each_par(self):
        async def f(x: int, _):
            await asyncio.sleep(0.01)
            return x * 2

        items = list(range(5))
        res = await for_each_par(items, lambda x: Effect(lambda ctx: f(x, ctx)), parallelism=2)._run(Context())
        self.assertEqual(res, [0, 2, 4, 6, 8])

