import unittest

from effectpy import Context, Effect, provide_service, service
from effectpy.core import Failure


class TestServicesEnv(unittest.IsolatedAsyncioTestCase):
    async def test_service_accessor_success(self):
        class Foo:
            def __init__(self, v: int):
                self.v = v

        L = provide_service(Foo, Foo(7))

        async def use(_):
            s = await service(Foo)._run(ctx)
            return s.v

        ctx = await L.build(Context())
        try:
            v = await Effect(use)._run(ctx)
            self.assertEqual(v, 7)
        finally:
            await L.teardown(ctx)

    async def test_service_accessor_missing_fails(self):
        class Bar:
            pass

        with self.assertRaises(Failure) as cm:
            await service(Bar)._run(Context())
        self.assertIsInstance(cm.exception.error, KeyError)

