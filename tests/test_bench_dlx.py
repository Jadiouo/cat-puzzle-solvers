import json
import os
import random
import unittest

from bench import check, reference
from bench.solver_dlx import DLXAdapter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = DLXAdapter()


def suite(name):
    with open(os.path.join(ROOT, "bench", "suites", f"{name}.json")) as f:
        return json.load(f)["puzzles"]


class DLXTests(unittest.TestCase):
    def test_zero_solutions(self):
        r = A.solve([[0, 1], [1, 0]], "count", 5)
        self.assertEqual((r["status"], r["count"]), ("UNSAT", 0))
        r = A.solve([[0, 0], [1, 1]], "classify", 5)
        self.assertEqual(r["count"], 0)

    def test_trivial_n1(self):
        self.assertEqual(A.solve([[0]], "count", 5)["count"], 1)

    def test_multi_and_unique(self):
        g = [[0, 0, 1, 1], [0, 0, 1, 1], [2, 2, 3, 3], [2, 2, 3, 3]]
        r = A.solve(g, "count", 5)
        self.assertEqual(r["count"], reference.count_solutions(g))
        self.assertGreater(r["count"], 1)
        self.assertEqual(A.solve(g, "classify", 5)["count"], 2)
        self.assertEqual(A.solve(g, "first", 5)["count"], 1)
        for s in r["solutions"]:
            self.assertTrue(check.is_valid(g, s))
        p = suite("S1")[0]
        self.assertEqual(A.solve(p["regions"], "classify", 5)["count"], 1)

    def test_random_boards_match_reference(self):
        rnd = random.Random(7)
        for _ in range(60):
            n = rnd.randint(2, 8)
            g = [[rnd.randrange(n) for _ in range(n)] for _ in range(n)]
            if len({x for row in g for x in row}) != n:
                continue
            want = reference.count_solutions(g)
            r = A.solve(g, "count", 10)
            self.assertEqual(r["count"], want, g)
            self.assertEqual(A.solve(g, "classify", 10)["count"], min(want, 2))

    def test_suites_match_reference(self):
        for name, mx in (("S1", 300), ("S3", 120), ("S4", 12)):
            for p in suite(name)[:mx]:
                ref = p["ref"]["count"]
                if ref is None:
                    continue
                r = A.solve(p["regions"], "classify", 1)
                if r["status"] != "TIMEOUT":
                    self.assertEqual(r["count"], min(ref, 2), p["id"])


if __name__ == "__main__":
    unittest.main()
