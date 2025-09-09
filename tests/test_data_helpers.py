import unittest

from effectpy import (
    Result, Ok, Err, result_from_either, result_to_either,
    Either, Left, Right,
    Validated, Valid, Invalid, validated_map2,
    Chunk,
)


class TestResult(unittest.TestCase):
    def test_result_map_and_then(self):
        r: Result[str, int] = Ok(2).map(lambda x: x + 1)
        self.assertTrue(isinstance(r, Ok))
        self.assertEqual(r.value, 3)
        r2 = r.and_then(lambda x: Ok(x * 2))
        self.assertEqual(r2.value, 6)
        e: Result[str, int] = Err("e").map(lambda x: x + 1)
        self.assertTrue(isinstance(e, Err))

    def test_result_either_roundtrip(self):
        e = Right[str, int](5)
        r = result_from_either(e)
        self.assertTrue(isinstance(r, Ok))
        e2 = result_to_either(r)
        self.assertTrue(isinstance(e2, Right))


class TestValidated(unittest.TestCase):
    def test_validated_ap_and_combine(self):
        v1 = Valid(2)
        v2 = Valid(3)
        comb = v1.combine(v2)
        self.assertTrue(isinstance(comb, Valid))
        self.assertEqual(comb.value, (2, 3))

        i1 = Invalid(["e1"])  # type: ignore[assignment]
        i2 = Invalid(["e2"])  # type: ignore[assignment]
        comb2 = i1.combine(i2)
        self.assertTrue(isinstance(comb2, Invalid))
        self.assertEqual(comb2.errors, ["e1", "e2"])  # type: ignore[attr-defined]

    def test_validated_map2(self):
        v1 = Valid(2); v2 = Valid(5)
        r = validated_map2(v1, v2, lambda a, b: a + b)
        self.assertTrue(isinstance(r, Valid))
        self.assertEqual(r.value, 7)


class TestChunk(unittest.TestCase):
    def test_chunk_ops(self):
        c = Chunk.of(1, 2, 3).map(lambda x: x + 1).filter(lambda x: x % 2 == 0)
        self.assertEqual(c.to_list(), [2, 4])
        d = c.append(6).extend([8])
        self.assertEqual(d.to_list(), [2, 4, 6, 8])

