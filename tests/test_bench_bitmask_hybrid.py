import json
import os
import random
import unittest

from bench import check, reference
from bench.build_suites import balanced_planted, random_connected
from bench.solver_bitmask import BitmaskAdapter, BitmaskRowAdapter
from bench.solver_hybrid import (HybridAdapter, HybridK2Adapter, HybridSAdapter,
                                 HybridT3Adapter)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = os.path.join(ROOT, "levelgen", "pool", "pool.json")
ADAPTERS = [BitmaskAdapter(), BitmaskRowAdapter(), HybridSAdapter(), HybridT3Adapter(),
            HybridAdapter(), HybridK2Adapter()]


def pool(k):
    with open(POOL) as f:
        return json.load(f)["puzzles"][:k]


class SmallCases(unittest.TestCase):
    def test_zero_solutions(self):
        for a in ADAPTERS:
            for g in ([[0, 1], [1, 0]], [[0, 0, 1], [0, 2, 1], [2, 2, 1]]):   # n=2,3 always 0
                for mode in ("first", "classify", "count"):
                    r = a.solve(g, mode, 5)
                    self.assertEqual((r["status"], r["count"], r["solutions"], r["complete"]),
                                     ("UNSAT", 0, [], True), (a.name, mode))

    def test_wrong_region_count_is_zero(self):
        for a in ADAPTERS:
            r = a.solve([[0, 0, 0, 0]] * 4, "count", 5)
            self.assertEqual((r["count"], r["status"]), (0, "UNSAT"), a.name)

    def test_trivial_n1(self):
        for a in ADAPTERS:
            r = a.solve([[0]], "count", 5)
            self.assertEqual((r["count"], r["solutions"]), (1, [[0]]), a.name)

    def test_unique(self):
        for a in ADAPTERS:
            for p in pool(5):
                for mode in ("first", "classify", "count"):
                    r = a.solve(p["regions"], mode, 10)
                    self.assertEqual((r["status"], r["count"], r["complete"]),
                                     ("SOLVED", 1, True), (a.name, p["id"], mode))
                    self.assertEqual(r["solutions"], [p["solution"]])

    def test_multiple(self):
        grid = random_connected(7, random.Random(0))
        for seed in range(30):                      # find a board with >= 3 solutions
            grid = random_connected(7, random.Random(seed))
            ref = reference.count_solutions(grid)
            if ref >= 3:
                break
        self.assertGreaterEqual(ref, 3)
        for a in ADAPTERS:
            self.assertEqual(a.solve(grid, "classify", 10)["count"], 2, a.name)
            self.assertEqual(a.solve(grid, "first", 10)["count"], 1, a.name)
            r = a.solve(grid, "count", 10)
            self.assertEqual(r["count"], ref, a.name)
            self.assertEqual(len({tuple(s) for s in r["solutions"]}), ref, a.name)
            for s in r["solutions"]:
                self.assertTrue(check.is_valid(grid, s))

    def test_random_boards_match_reference(self):
        for i in range(25):
            n = 5 + i % 5
            grid = random_connected(n, random.Random(100 + i))
            ref = reference.count_solutions(grid)
            for a in ADAPTERS:
                self.assertEqual(a.solve(grid, "count", 20)["count"], ref, (a.name, i))
                self.assertEqual(a.solve(grid, "classify", 20)["count"], min(ref, 2), (a.name, i))

    def test_noncontiguous_and_relabelled_regions(self):
        grid, _ = balanced_planted(8, random.Random(5))
        ref = reference.count_solutions(grid)
        perm = [3, 0, 7, 1, 6, 2, 5, 4]
        g2 = [[perm[x] for x in row] for row in grid]
        for a in ADAPTERS:
            self.assertEqual(a.solve(g2, "count", 20)["count"], ref, a.name)

    def test_timeout_reported(self):
        grid, _ = balanced_planted(16, random.Random(1))
        for a in ADAPTERS:
            r = a.solve(grid, "count", 0.05)
            self.assertIn(r["status"], ("TIMEOUT", "SOLVED"), a.name)
            if r["status"] == "TIMEOUT":
                self.assertIsNone(r["count"])
                self.assertFalse(r["complete"])


if __name__ == "__main__":
    unittest.main()
