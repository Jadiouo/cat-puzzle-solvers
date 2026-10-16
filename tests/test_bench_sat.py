import importlib.util
import json
import os
import random
import unittest

from bench import check, reference

HAVE = all(importlib.util.find_spec(m) for m in ("pysat", "ortools"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def suite(name):
    with open(os.path.join(ROOT, "bench", "suites", f"{name}.json")) as f:
        return json.load(f)["puzzles"]


def random_board(n, rng):
    """Random connected-ish region labelling via random seeds + flood growth (N regions)."""
    g = [[-1] * n for _ in range(n)]
    cells = [(r, c) for r in range(n) for c in range(n)]
    rng.shuffle(cells)
    for i in range(n):
        r, c = cells[i]
        g[r][c] = i
    free = [x for x in cells if g[x[0]][x[1]] < 0]
    while free:
        r, c = free.pop()
        nb = [g[r + dr][c + dc] for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
              if 0 <= r + dr < n and 0 <= c + dc < n and g[r + dr][c + dc] >= 0]
        if nb:
            g[r][c] = rng.choice(nb)
        else:
            free.insert(0, (r, c))
    return g


@unittest.skipUnless(HAVE, "pysat/ortools not installed (use .venv)")
class SatAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from bench import solver_sat
        cls.adapters = solver_sat.ADAPTERS

    def check_one(self, regions, ref, label):
        for name, ad in self.adapters.items():
            for mode in ("first", "classify", "count"):
                res = ad.solve(regions, mode, 20)
                tag = f"{label} {name}/{mode}"
                self.assertTrue(res["complete"], tag)
                want = {"first": min(ref, 1), "classify": min(ref, 2), "count": ref}[mode]
                self.assertEqual(res["count"], want, tag)
                self.assertEqual(res["status"], "SOLVED" if want else "UNSAT", tag)
                for s in res["solutions"]:
                    self.assertTrue(check.is_valid(regions, s), tag)
                self.assertEqual(len({tuple(s) for s in res["solutions"]}), len(res["solutions"]))
                if mode == "count":
                    self.assertEqual(len(res["solutions"]), ref, tag)
                for k in ("build_s", "solve_s", "import_s"):
                    self.assertIn(k, res)

    def test_zero_one_many_from_suites(self):
        picked = {}
        for sn in ("S3", "S4", "S1"):
            for p in suite(sn):
                c = (p.get("ref") or {}).get("count")
                if c is None or p["n"] > 8:
                    continue
                key = 0 if c == 0 else 1 if c == 1 else 2
                if key not in picked or (key == 2 and c < picked[key][1]):
                    picked[key] = (p, c)
        self.assertIn(0, picked)
        self.assertIn(1, picked)
        for p, c in picked.values():
            self.check_one(p["regions"], c, p["id"])

    def test_tiny_boards(self):
        self.check_one([[0]], 1, "1x1")
        self.check_one([[0, 1], [0, 1]], 0, "2x2")          # neighbours always touch
        self.check_one([[0, 0, 1], [0, 1, 1], [2, 2, 2]], reference.count_solutions(
            [[0, 0, 1], [0, 1, 1], [2, 2, 2]]), "3x3")

    def test_random_boards_vs_reference(self):
        rng = random.Random(7)
        seen = set()
        for i in range(25):
            n = rng.choice((4, 5, 6, 7))
            b = random_board(n, rng)
            ref = reference.count_solutions(b)
            seen.add(min(ref, 2))
            self.check_one(b, ref, f"rand{i}")
        self.assertTrue({0, 1} <= seen or len(seen) >= 2, seen)

    def test_timeout_reported_not_wrong(self):
        big = max((p for p in suite("S4")), key=lambda p: p["n"])
        res = self.adapters["cpsat_w1"].solve(big["regions"], "count", 0.05)
        self.assertIn(res["status"], ("TIMEOUT", "SOLVED", "UNSAT"))
        if res["status"] == "TIMEOUT":
            self.assertFalse(res["complete"])
            self.assertIsNone(res["count"])


if __name__ == "__main__":
    unittest.main()
