import unittest
import asyncio

from effectpy.core import Effect, scoped
from effectpy.context import Context
from effectpy.layer import from_resource


class TestResourcesScopeHelpers(unittest.IsolatedAsyncioTestCase):
    async def test_scoped_helper_closes_scope(self):
        events: list[str] = []

        async def make_scope_effect(scope):
            async def finalizer():
                events.append("fin")

            # Register a finalizer via the scope API directly
            await scope.add_finalizer(lambda: _async_mark(events, "fin"))
            async def body(_):
                events.append("run")
                return 1

            return Effect(body)

        v = await scoped(make_scope_effect)._run(Context())
        self.assertEqual(v, 1)
        self.assertIn("fin", events)

    async def test_provide_scoped_uses_layer_scope(self):
        events: list[str] = []

        class S:
            pass

        async def mk(_):
            events.append("mk"); return S()

        async def close(_s: S):
            events.append("close")

        L = from_resource(S, mk, close)

        async def use(ctx: Context):
            _ = ctx.get(S)
            return 42

        eff = Effect(use).provide_scoped(L)
        v = await eff._run(Context())
        self.assertEqual(v, 42)
        self.assertEqual(events, ["mk", "close"])


async def _async_mark(lst, tag):
    lst.append(tag)

