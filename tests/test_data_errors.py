import unittest

from effectpy import Option, Some, NONE, from_nullable, Either, Left, Right, Duration
from effectpy.core import Effect
from effectpy.context import Context
from effectpy.runtime import Runtime


class TestOptionEither(unittest.TestCase):
    def test_option(self):
        self.assertTrue(isinstance(Some(1), Option))
        self.assertEqual(Some(2).map(lambda x: x+1).value, 3)
        self.assertTrue(NONE.is_none())
        self.assertEqual(from_nullable(None).get_or_else(5), 5)

    def test_either(self):
        r = Right[int, int](2).map(lambda x: x*3)
        self.assertTrue(isinstance(r, Right))
        self.assertEqual(r.value, 6)
        l = Left[str, int]("e").map(lambda x: x+1)
        self.assertTrue(isinstance(l, Left))
        self.assertEqual(l.error, "e")

    def test_duration(self):
        d = Duration.millis(500) + Duration.seconds_(0.5)
        self.assertEqual(str(d), "1.000s")


class TestErrorAnnotations(unittest.IsolatedAsyncioTestCase):
    async def test_annotate_failure_propagates_to_cause(self):
        async def boom(_):
            from effectpy.core import Failure
            raise Failure("bad")

        eff = Effect(boom).annotate("path=/foo").annotate("op=test")
        rt = Runtime(Context())
        f = rt.fork(eff)
        ex = await f.await_()
        self.assertFalse(ex.success)
        rendered = ex.cause.render()
        self.assertIn("@ path=/foo", rendered)
        self.assertIn("@ op=test", rendered)

