import json
import os
import random
import unittest

from bench import check

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "bench", "suites", "S5.json")


def connected(grid, g):
    n = len(grid)
    cells = {(r, c) for r in range(n) for c in range(n) if grid[r][c] == g}
    st = [next(iter(cells))]
    seen = set(st)
    while st:
        r, c = st.pop()
        for q in ((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)):
            if q in cells and q not in seen:
                seen.add(q)
                st.append(q)
    return seen == cells


class S5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PATH) as f:
            cls.d = json.load(f)

    def test_format(self):
        self.assertEqual(self.d["suite"], "S5")
        ids = [p["id"] for p in self.d["puzzles"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(self.d["puzzles"])
        for p in self.d["puzzles"]:
            n = p["n"]
            self.assertIn(n, range(11, 17))
            self.assertEqual(len(p["regions"]), n)
            self.assertTrue(all(len(r) == n for r in p["regions"]))
            self.assertEqual(p["ref"]["count"], 1)
            self.assertIn("SAT", p["ref"]["source"])
            self.assertIn("bitmask", p["ref"]["source"])

    def test_sample_valid(self):
        ps = self.d["puzzles"]
        for p in random.Random(0).sample(ps, min(12, len(ps))):
            g, n = p["regions"], p["n"]
            self.assertEqual({x for r in g for x in r}, set(range(n)))
            self.assertEqual(check.violations(g, p["planted"]), [])
            sizes = [sum(r.count(k) for r in g) for k in range(n)]
            self.assertTrue(all(3 <= z <= 2 * n for z in sizes), sizes)
            self.assertTrue(all(connected(g, k) for k in range(n)))

    def test_sample_unique(self):
        from bench.solver_bitmask import BitmaskAdapter
        for p in self.d["puzzles"][::7]:
            r = BitmaskAdapter().solve(p["regions"], "classify", 30)
            self.assertEqual((r["count"], r["solutions"][0]), (1, p["planted"]))


if __name__ == "__main__":
    unittest.main()
