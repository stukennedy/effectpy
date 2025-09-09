import asyncio
import unittest

from effectpy.core import Effect, Failure
from effectpy.context import Context


class TestCoreExtras(unittest.IsolatedAsyncioTestCase):
    async def test_map_error(self):
        eff = Effect(lambda _: (_ for _ in ()).throw(Failure("bad")))  # raise Failure("bad") in async
        eff2 = eff.map_error(lambda e: f"x:{e}")
        with self.assertRaises(Failure) as cm:
            await eff2._run(Context())
        self.assertEqual(cm.exception.error, "x:bad")

    async def test_either_success_and_failure(self):
        ok = Effect(lambda _: _async_const(7))
        bad = Effect(lambda _: (_ for _ in ()).throw(Failure("nope")))

        v1 = await ok.fold(lambda e: ("left", e), lambda a: ("right", a))._run(Context())
        v2 = await bad.fold(lambda e: ("left", e), lambda a: ("right", a))._run(Context())
        self.assertEqual(v1, ("right", 7))
        self.assertEqual(v2, ("left", "nope"))

    async def test_refine_or_die(self):
        eff = Effect(lambda _: (_ for _ in ()).throw(Failure({"kind": "A", "msg": "xxx"})))

        # refine matches -> transforms error
        ref_ok = eff.refine_or_die(lambda e: e if e.get("kind") == "A" else None)
        with self.assertRaises(Failure) as cm1:
            await ref_ok._run(Context())
        self.assertEqual(cm1.exception.error["kind"], "A")

        # refine misses -> die (RuntimeError)
        ref_die = eff.refine_or_die(lambda e: None)
        with self.assertRaises(RuntimeError):
            await ref_die._run(Context())

    async def test_on_error_runs_side_effect(self):
        box = {"n": 0}

        async def side(_):
            box["n"] += 1

        eff = Effect(lambda _: (_ for _ in ()).throw(Failure("boom")))
        with self.assertRaises(Failure):
            await eff.on_error(lambda e: Effect(side))._run(Context())
        self.assertEqual(box["n"], 1)

    async def test_on_interrupt_runs_side_effect(self):
        flag = {"done": False}

        async def long(_):
            await asyncio.sleep(1)

        async def side(_):
            flag["done"] = True

        eff = Effect(long).on_interrupt(Effect(side))
        task = asyncio.create_task(eff._run(Context()))
        await asyncio.sleep(0.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertTrue(flag["done"])


async def _async_const(x):
    await asyncio.sleep(0)
    return x

