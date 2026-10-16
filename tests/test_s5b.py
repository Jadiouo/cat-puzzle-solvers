import json
import os
import unittest

from bench import check
from tests.test_s5 import connected

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "bench", "suites", "S5b.json")


class S5b(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(PATH) as f:
            cls.d = json.load(f)

    def test_format_valid(self):
        self.assertEqual(self.d["suite"], "S5b")
        ids = [p["id"] for p in self.d["puzzles"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(ids)
        for p in self.d["puzzles"]:
            g, n = p["regions"], p["n"]
            self.assertIn(n, (12, 14, 16))
            self.assertEqual(len(g), n)
            self.assertTrue(all(len(r) == n for r in g))
            self.assertEqual(p["ref"]["count"], 1)
            self.assertIn("SAT", p["ref"]["source"])
            self.assertIn("CP-SAT", p["ref"]["source"])
            self.assertEqual({x for r in g for x in r}, set(range(n)))
            self.assertEqual(check.violations(g, p["planted"]), [])
            sizes = [sum(r.count(k) for r in g) for k in range(n)]
            self.assertTrue(all(3 <= z <= 2 * n for z in sizes), sizes)
            self.assertTrue(all(connected(g, k) for k in range(n)))


if __name__ == "__main__":
    unittest.main()
