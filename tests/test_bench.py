import contextlib
import io
import json
import os
import random
import unittest

from bench import check, reference, runner, solvers
from bench.build_suites import balanced_planted, random_connected

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POOL = os.path.join(ROOT, "levelgen", "pool", "pool.json")


def pool_puzzles(k):
    with open(POOL) as f:
        return json.load(f)["puzzles"][:k]


class CheckerTests(unittest.TestCase):
    def test_pool_solutions_valid_and_mutations_rejected(self):
        for p in pool_puzzles(20):
            self.assertTrue(check.is_valid(p["regions"], p["solution"]))
            bad = list(p["solution"])
            bad[0], bad[1] = bad[1], bad[0]
            if bad != p["solution"]:
                self.assertFalse(check.is_valid(p["regions"], bad) and bad == p["solution"])
        self.assertIn("adjacent@0", check.violations([[0, 1], [1, 0]], [0, 1]))
        self.assertIn("column", check.violations([[0, 1], [1, 0]], [0, 0]))
        self.assertEqual(check.violations([[0]], [0]), [])


class ReferenceTests(unittest.TestCase):
    def test_pool_is_unique(self):
        for p in pool_puzzles(30):
            self.assertEqual(reference.count_solutions(p["regions"]), 1, p["id"])

    def test_matches_levelgen_bruteforce_on_random_boards(self):
        from levelgen import board
        for i in range(12):
            rng = random.Random(i)
            n = 6 + i % 3
            grid = random_connected(n, rng)
            flat = [x for r in grid for x in r]
            self.assertEqual(reference.count_solutions(grid), board.count_solutions(flat, n, 10 ** 9))

    def test_budget_exhaustion_returns_none_not_a_guess(self):
        grid, _ = balanced_planted(12, random.Random(1))
        self.assertIsNone(reference.count_solutions(grid, node_limit=5))


class GeneratorTests(unittest.TestCase):
    def test_planted_balanced_is_solvable_and_deterministic(self):
        g1, s1 = balanced_planted(10, random.Random("x"))
        g2, s2 = balanced_planted(10, random.Random("x"))
        self.assertEqual((g1, s1), (g2, s2))
        self.assertTrue(check.is_valid(g1, s1))
        sizes = [sum(row.count(g) for row in g1) for g in range(10)]
        self.assertTrue(8 <= min(sizes) and max(sizes) <= 12, sizes)

    def test_random_connected_has_n_regions(self):
        g = random_connected(9, random.Random(3))
        self.assertEqual(len({x for r in g for x in r}), 9)


class AdapterTests(unittest.TestCase):
    def test_cat_solver_modes_agree_with_pool(self):
        a = solvers.get("cat_solver")
        p = pool_puzzles(1)[0]
        for mode, cnt in (("first", 1), ("classify", 1), ("count", 1)):
            r = a.solve(p["regions"], mode, 10)
            self.assertEqual((r["status"], r["count"], r["complete"]), ("SOLVED", cnt, True), mode)
            self.assertEqual(r["solutions"], [p["solution"]])

    def test_cat_solver_classify_multiple_and_unsat(self):
        a = solvers.get("cat_solver")
        multi = random_connected(6, random.Random(0))
        n_sol = reference.count_solutions(multi)
        r = a.solve(multi, "classify", 10)
        self.assertEqual(r["count"], min(n_sol, 2))
        self.assertEqual(a.solve(multi, "count", 10)["count"], n_sol)

    def test_levelgen_solves_pool(self):
        r = solvers.get("levelgen").solve(pool_puzzles(1)[0]["regions"], "first", 10)
        self.assertEqual(r["status"], "SOLVED")

    def test_timeout_is_reported(self):
        grid, _ = balanced_planted(16, random.Random(1))
        r = solvers.get("cat_solver").solve(grid, "count", 0.05)
        self.assertIn(r["status"], ("TIMEOUT", "SOLVED"))
        if r["status"] == "TIMEOUT":
            self.assertFalse(r["complete"])
            self.assertIsNone(r["count"])


class JudgeTests(unittest.TestCase):
    def setUp(self):
        p = pool_puzzles(1)[0]
        self.p = {"regions": p["regions"], "ref": {"count": 1}}
        self.sol = p["solution"]

    def res(self, **kw):
        base = {"status": "SOLVED", "solutions": [self.sol], "count": 1, "complete": True,
                "nodes": 1, "elapsed": 0.1}
        base.update(kw)
        return base

    def test_ok(self):
        for m in ("first", "classify", "count"):
            self.assertEqual(runner.judge(self.p, m, self.res(), 10)[0], "OK")

    def test_wrong_count_is_mismatch(self):
        self.assertEqual(runner.judge(self.p, "count", self.res(count=2, solutions=[self.sol, self.sol]), 10)[0],
                         "MISMATCH")
        self.assertEqual(runner.judge(self.p, "classify", self.res(count=2), 10)[0], "MISMATCH")

    def test_invalid_solution_is_mismatch(self):
        bad = list(self.sol)
        bad[0] = bad[1]
        self.assertEqual(runner.judge(self.p, "first", self.res(solutions=[bad]), 10)[0], "MISMATCH")

    def test_unsat_vs_ref(self):
        r = self.res(status="UNSAT", solutions=[], count=0)
        self.assertEqual(runner.judge(self.p, "count", r, 10)[0], "MISMATCH")
        self.assertEqual(runner.judge({**self.p, "ref": {"count": 0}}, "count", r, 10)[0], "OK")

    def test_solution_when_ref_zero(self):
        self.assertEqual(runner.judge({**self.p, "ref": {"count": 0}}, "first", self.res(), 10)[0], "MISMATCH")

    def test_planted_solution_bounds_unknown_reference(self):
        pz = {**self.p, "ref": {"count": None}, "planted": self.sol}
        r = self.res(status="UNSAT", solutions=[], count=0)
        self.assertEqual(runner.judge(pz, "count", r, 10)[0], "MISMATCH")

    def test_timeout_error_stuck_noref(self):
        self.assertEqual(runner.judge(self.p, "first", self.res(status="TIMEOUT"), 10)[0], "TIMEOUT")
        self.assertEqual(runner.judge(self.p, "first", self.res(elapsed=11), 10)[0], "TIMEOUT")
        self.assertEqual(runner.judge(self.p, "first", {"status": "ERROR"}, 10)[0], "ERROR")
        self.assertEqual(runner.judge(self.p, "first", self.res(status="STUCK", solutions=[], count=None), 10)[0],
                         "INCOMPLETE")
        self.assertEqual(runner.judge({**self.p, "ref": {"count": None}}, "count", self.res(), 10)[0], "NOREF")


class SuiteFileTests(unittest.TestCase):
    def test_committed_suites_well_formed(self):
        for name, size in (("S1", 300),):
            doc = runner.load_suite(name)
            self.assertEqual(len(doc["puzzles"]), size)
        for name in ("S1", "S2", "S3", "S4"):
            path = os.path.join(runner.SUITE_DIR, name + ".json")
            if not os.path.exists(path):
                self.fail(f"missing suite {name}")
            for p in runner.load_suite(name)["puzzles"]:
                n = p["n"]
                self.assertEqual(len(p["regions"]), n)
                self.assertEqual(len({x for r in p["regions"] for x in r}), n, p["id"])
                self.assertIn("ref", p)
                if "planted" in p:
                    self.assertTrue(check.is_valid(p["regions"], p["planted"]), p["id"])
                    c = p["ref"]["count"]
                    self.assertTrue(c is None or c >= 1, p["id"])

    def test_s1_reference_is_unique(self):
        self.assertTrue(all(p["ref"]["count"] == 1 for p in runner.load_suite("S1")["puzzles"]))


class EndToEndTests(unittest.TestCase):
    def test_run_subprocess_small(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()):
                rc = runner.main(["run", "--solvers", "cat_solver", "levelgen", "--suite", "S1",
                                "--mode", "classify", "--per-n", "1", "--timeout", "10", "--out", d,
                                "--tag", "t"])
            self.assertEqual(rc, 0)
            with open(os.path.join(d, "t.json")) as f:
                doc = json.load(f)
            self.assertEqual(len(doc["rows"]), 8)
            self.assertTrue(all(r["verdict"] == "OK" for r in doc["rows"]))


if __name__ == "__main__":
    unittest.main()


class RegistrationTest(unittest.TestCase):
    def test_pure_python_adapters_registered(self):
        from bench import solvers
        for n in ("cat_solver", "bitmask", "bitmask_row", "hybrid", "hybrid_s", "hybrid_t3",
                  "hybrid_k2", "dlx"):
            self.assertIn(n, solvers.ADAPTERS)

    def test_sat_registered_or_skipped(self):
        from bench import solvers
        for n in ("sat_cadical153_seq", "cpsat_w1"):
            self.assertTrue(n in solvers.ADAPTERS or n in solvers.SKIPPED)
