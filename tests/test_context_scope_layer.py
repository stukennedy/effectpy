import asyncio
import unittest

from effectpy.context import Context
from effectpy.scope import Scope
from effectpy.layer import Layer, from_resource


class TestContext(unittest.TestCase):
    def test_add_and_get(self):
        class S: pass
        ctx = Context().add(S, S())
        self.assertIsInstance(ctx.get(S), S)

    def test_missing_raises(self):
        class S: pass
        with self.assertRaises(KeyError):
            Context().get(S)


class TestScope(unittest.IsolatedAsyncioTestCase):
    async def test_finalizers_run_in_lifo_order(self):
        order: list[int] = []
        s = Scope()
        await s.add_finalizer(lambda: _async_append(order, 1))
        await s.add_finalizer(lambda: _async_append(order, 2))
        await s.close()
        self.assertEqual(order, [2, 1])

    async def test_add_after_close_runs_immediately(self):
        s = Scope()
        called = {"n": 0}
        await s.close()
        await s.add_finalizer(lambda: _async_inc(called))
        self.assertEqual(called["n"], 1)


async def _async_append(lst, v):
    lst.append(v)


async def _async_inc(box):
    box["n"] += 1


class TestLayer(unittest.IsolatedAsyncioTestCase):
    async def test_from_resource_build_and_teardown(self):
        events: list[str] = []

        class S:
            def __init__(self):
                events.append("mk")

        async def mk(_):
            return S()

        async def close(_s: S):
            events.append("close")

        L = from_resource(S, mk, close)
        base = Context()
        scope = Scope()
        ctx = await L.build_scoped(base, scope)
        self.assertIsInstance(ctx.get(S), S)
        await scope.close()
        self.assertEqual(events, ["mk", "close"])

    async def test_composition_sequential_add(self):
        class A: pass
        class B: pass
        async def mk_a(_): return A()
        async def close_a(_): return None
        async def mk_b(_): return B()
        async def close_b(_): return None
        LA = from_resource(A, mk_a, close_a)
        LB = from_resource(B, mk_b, close_b)
        L = LA + LB
        ctx = await L.build(Context())
        self.assertIsInstance(ctx.get(A), A)
        self.assertIsInstance(ctx.get(B), B)

    async def test_parallel_merge_or(self):
        class A: pass
        class B: pass
        async def mk_a(_): return A()
        async def close_a(_): return None
        async def mk_b(_): return B()
        async def close_b(_): return None
        LA = from_resource(A, mk_a, close_a)
        LB = from_resource(B, mk_b, close_b)
        L = LA | LB
        scope = Scope()
        ctx = await L.build_scoped(Context(), scope)
        try:
            self.assertIsInstance(ctx.get(A), A)
            self.assertIsInstance(ctx.get(B), B)
        finally:
            await scope.close()

