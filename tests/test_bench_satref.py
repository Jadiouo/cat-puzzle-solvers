import importlib.util
import json
import os
import unittest

from bench import check

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAVE = all(importlib.util.find_spec(m) for m in ("pysat", "ortools"))


@unittest.skipUnless(HAVE, "needs pysat + ortools (.venv/bin/python)")
class SatRefTests(unittest.TestCase):
    def test_unique_pool_puzzle_and_zero_solution_board(self):
        from bench import satref
        pool = json.load(open(os.path.join(ROOT, "levelgen", "pool", "pool.json")))["puzzles"][:3]
        for p in pool:
            r = satref.judge_one(p["regions"])
            self.assertTrue(r["confirmed"])
            self.assertEqual(r["class"], 1)
            self.assertEqual(r["cadical153"]["solutions"], [p["solution"]])
            self.assertTrue(check.is_valid(p["regions"], r["cpsat"]["solutions"][0]))
        # 4x4 with a single 4-cell region cannot be a valid puzzle: region ids 0..3 but no placement
        grid = [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0], [1, 2, 3, 3]]
        r = satref.judge_one(grid)
        self.assertTrue(r["confirmed"])
        self.assertEqual(r["class"], 0)

    def test_published_file_is_all_confirmed_and_solutions_valid(self):
        d = json.load(open(os.path.join(ROOT, "bench", "suites", "S3_S4_satref.json")))["puzzles"]
        suite = {}
        for s in ("S1", "S2", "S3", "S4"):
            for p in json.load(open(os.path.join(ROOT, "bench", "suites", f"{s}.json")))["puzzles"]:
                suite[p["id"]] = p
        for pid, r in d.items():
            self.assertTrue(r["confirmed"], pid)
            for e in ("cadical153", "cpsat"):
                for sol in r[e]["solutions"]:
                    self.assertTrue(check.is_valid(suite[pid]["regions"], sol), pid)


if __name__ == "__main__":
    unittest.main()
