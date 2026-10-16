import json
import os
import unittest

from bench import check
from tests.test_s5 import connected

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "bench", "suites", "S6.json")


class S6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PATH) as f:
            cls.d = json.load(f)

    def test_format_valid(self):
        self.assertEqual(self.d["suite"], "S6")
        ps = self.d["puzzles"]
        ids = [p["id"] for p in ps]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(ps)
        for p in ps:
            g, n = p["regions"], p["n"]
            self.assertIn(n, (10, 12, 14))
            self.assertIn(p["group"], ("S6-bm", "S6-hy", "S6-sat"))
            self.assertEqual(len(g), n)
            self.assertTrue(all(len(r) == n for r in g))
            self.assertEqual(p["ref"]["count"], 1)
            self.assertTrue(p["measure"]["unique"])
            self.assertEqual({x for r in g for x in r}, set(range(n)))
            self.assertEqual(check.violations(g, p["planted"]), [])
            sizes = [sum(r.count(k) for r in g) for k in range(n)]
            self.assertTrue(all(3 <= z <= 2 * n for z in sizes), sizes)
            self.assertTrue(all(connected(g, k) for k in range(n)))

    def test_unique_bitmask(self):
        from bench.solver_bitmask import BitmaskAdapter
        for p in self.d["puzzles"][:6]:
            r = BitmaskAdapter().solve(p["regions"], "classify", 10)
            self.assertEqual(r["count"], 1)
            self.assertEqual(r["solutions"][0], p["planted"])


if __name__ == "__main__":
    unittest.main()
