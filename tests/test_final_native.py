import importlib.util
import json
import os
import unittest

from bench import make_table_native as mt
from bench import runner, solver_native, solvers

HAVE_SAT = all(importlib.util.find_spec(m) for m in ("pysat", "ortools"))
G = [[0, 0, 1, 1], [0, 2, 1, 1], [3, 2, 2, 1], [3, 3, 2, 2]]
P = {"id": "x", "n": 4, "regions": G, "ref": {"count": 0, "source": "bench.reference bitmask DFS"}}


def fake(seq):
    it = iter(seq)
    return lambda sv, p, mode, to: dict(next(it))


class Registration(unittest.TestCase):
    def test_native_registered_or_skipped_with_hint(self):
        for name in solver_native.NATIVE_ADAPTERS:
            if solver_native.available():
                self.assertIn(name, solvers.ADAPTERS)
            else:
                self.assertIn("make -C native", solvers.SKIPPED[name])

    @unittest.skipUnless(solver_native.available(), "native binary not built (make -C native)")
    def test_native_count_mode_is_not_a_mismatch(self):
        res = solvers.get("native_dlx").solve(G, "count", 5)
        self.assertTrue(res["count_only"])
        v, _ = runner.judge({"regions": G, "ref": {"count": res["count"], "source": "x"}}, "count", res, 10)
        self.assertEqual(v, "OK")


class JudgeClassOnly(unittest.TestCase):
    def test_class_only_count_mode_compares_min2(self):
        pz = {"regions": G, "ref": {"count": 2, "class_only": True, "source": "sat"}}
        res = {"status": "SOLVED", "solutions": [], "count": 12345, "n_solutions": 0, "count_only": True,
               "elapsed": 1.0}
        self.assertEqual(runner.judge(pz, "count", res, 10)[0], "OK")
        res["count"] = 1
        self.assertEqual(runner.judge(pz, "count", res, 10)[0], "MISMATCH")

    def test_exact_ref_count_still_exact(self):
        pz = {"regions": G, "ref": {"count": 7, "source": "bench.reference"}}
        res = {"status": "SOLVED", "solutions": [], "count": 8, "n_solutions": 0, "count_only": True, "elapsed": 1.0}
        self.assertEqual(runner.judge(pz, "count", res, 10)[0], "MISMATCH")

    def test_apply_satref_patches_only_non_independent(self):
        doc = runner.load_suite("S3")
        before = {p["id"]: p["ref"] for p in doc["puzzles"]}
        k = runner.apply_satref(doc)
        self.assertEqual(k, 28)   # 21 unknown + 7 cat_solver-only references
        for p in doc["puzzles"]:
            if p["ref"].get("class_only"):
                self.assertFalse(str(before[p["id"]].get("source", "")).startswith("bench.reference"))
            else:
                self.assertEqual(p["ref"], before[p["id"]])


class CoreTime(unittest.TestCase):
    def ok(self, el, solve=None):
        d = {"status": "UNSAT", "solutions": [], "count": 0, "complete": True, "nodes": 1, "elapsed": el}
        if solve is not None:
            d.update(solve_s=solve, build_s=el - solve)
        return d

    def test_native_core_equals_elapsed(self):
        res, *_ = runner.run_repeats("s", P, "count", 10.0, 3, fake([self.ok(1), self.ok(3), self.ok(2)]))
        self.assertEqual(res["core_s"], 2)

    def test_sat_core_is_solve_median_not_build(self):
        res, *_ = runner.run_repeats("s", P, "count", 10.0, 3,
                                     fake([self.ok(5, 1), self.ok(7, 3), self.ok(6, 2)]))
        self.assertEqual((res["core_s"], res["solve_s"], res["elapsed"], res["build_s"]), (2, 2, 6, 4))

    def test_timeout_core_is_limit(self):
        to = {"status": "TIMEOUT", "solutions": [], "count": None, "complete": False, "nodes": None, "elapsed": 10.0}
        res, *_ = runner.run_repeats("s", P, "count", 10.0, 3, fake([to]))
        self.assertEqual(res["core_s"], 10.0)


@unittest.skipUnless(HAVE_SAT, "pysat/ortools not installed (use .venv)")
class WorkCounters(unittest.TestCase):
    def test_sat_and_cpsat_report_counters(self):
        from bench import solver_sat
        a = solver_sat.ADAPTERS["sat_cadical153_seq"].solve(G, "classify", 5)
        for k in ("conflicts", "decisions", "propagations"):
            self.assertIsInstance(a[k], int)
        b = solver_sat.ADAPTERS["cpsat_w1"].solve(G, "classify", 5)
        for k in ("branches", "conflicts"):
            self.assertIsInstance(b[k], int)


class TableHelpers(unittest.TestCase):
    def row(self, sv, core, to=False, nodes=None):
        return {"solver": sv, "core": core, "e2e": core, "to": to, "nodes": nodes, "conflicts": None,
                "decisions": None, "propagations": None, "branches": None}

    def test_cell_par2_and_timeouts(self):
        g = [self.row("a", 1.0), self.row("a", 3.0), self.row("a", 10.0, to=True)]
        s, rank = mt.cell(g, "core", 10.0)
        self.assertEqual(s, "2.00s / 3.00s / 1/3 / 8.00s")
        self.assertAlmostEqual(rank[0], (1 + 3 + 20) / 3)

    def test_ft_units(self):
        self.assertEqual((mt.ft(2e-6), mt.ft(2.5e-3), mt.ft(1.234)), ("2us", "2.5ms", "1.23s"))

    def test_work_table_excludes_timeouts(self):
        rows = [dict(self.row("native_bitmask", 1, nodes=10), suite="S5", n=11),
                dict(self.row("native_bitmask", 1, nodes=30), suite="S5", n=11),
                dict(self.row("native_bitmask", 10, to=True, nodes=999), suite="S5", n=11)]
        t = mt.work_table(rows, lambda r: (r["suite"], r["n"]), [("S5", 11)], "k")
        self.assertIn("20 / 30", t[-1])


if __name__ == "__main__":
    unittest.main()
