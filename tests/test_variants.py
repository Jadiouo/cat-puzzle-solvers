"""Solver variants: native_match / native_rr / native_match_rr and the SAT encoding/solver variants."""
import importlib.util
import json
import os
import unittest

from bench import solvers  # noqa: F401  (import first: avoids a circular import)
from bench import solver_native

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NATIVE_NEW = ("native_match", "native_rr", "native_match_rr")
SAT_NEW = ("sat_cadical153_pairwise", "sat_cadical153_ladder", "sat_cadical153_totalizer",
           "sat_cadical153_bitwise", "sat_cadical195_seq", "sat_glucose4_seq", "sat_minisat22_seq")
HAVE_NATIVE = solver_native.available()
HAVE_PYSAT = importlib.util.find_spec("pysat") is not None


def _suite(name):
    with open(os.path.join(ROOT, "bench", "suites", name + ".json")) as f:
        return json.load(f)["puzzles"]


def _small(k=12):
    ps = [p for p in _suite("S1") if p["n"] <= 8]
    return ps[::max(1, len(ps) // k)][:k]


class Registration(unittest.TestCase):
    def test_names_registered(self):
        names = (list(SAT_NEW) if HAVE_PYSAT else []) + (list(NATIVE_NEW) if HAVE_NATIVE else [])
        for n in names:
            self.assertIn(n, solvers.ADAPTERS, solvers.SKIPPED.get(n))

    def test_rr_has_no_count_mode(self):
        for n in ("native_rr", "native_match_rr"):
            self.assertNotIn("count", solver_native.NATIVE_ADAPTERS[n].modes)
        self.assertIn("count", solver_native.NATIVE_ADAPTERS["native_match"].modes)


@unittest.skipUnless(HAVE_NATIVE, "native/build/cat_native not built (make -C native)")
class NativeVariants(unittest.TestCase):
    def test_counts_match_bitmask(self):
        pz = [(p["id"], p["regions"]) for p in _small()]
        for mode in ("first", "classify", "count"):
            base = solver_native.run_batch("bitmask", mode, 20, pz)
            for sv in ("match", "rr", "match_rr"):
                if sv != "match" and mode == "count":
                    continue
                got = solver_native.run_batch(sv, mode, 20, pz)
                for b, g in zip(base, got):
                    with self.subTest(sv=sv, mode=mode, id=b["id"]):
                        self.assertEqual((b["status"], b["count"]), (g["status"], g["count"]))

    def test_match_nodes_le_bitmask_S1(self):
        pz = [(p["id"], p["regions"]) for p in _suite("S1")]
        for mode in ("classify", "count"):
            base = solver_native.run_batch("bitmask", mode, 20, pz)
            mat = solver_native.run_batch("match", mode, 20, pz)
            worse = [(b["id"], b["nodes"], m["nodes"]) for b, m in zip(base, mat) if m["nodes"] > b["nodes"]]
            self.assertEqual(worse, [], mode)
            self.assertTrue(any(m["nodes"] < b["nodes"] for b, m in zip(base, mat)), "pruning never fired")

    def test_rr_reproducible_and_count_error(self):
        pz = [(p["id"], p["regions"]) for p in _suite("S1") if p["n"] >= 9][:15]
        for sv in ("rr", "match_rr"):
            a = solver_native.run_batch(sv, "classify", 20, pz)
            b = solver_native.run_batch(sv, "classify", 20, pz)
            self.assertEqual([(r["nodes"], r["solutions"]) for r in a], [(r["nodes"], r["solutions"]) for r in b])
            c = solver_native.run_batch(sv, "count", 20, pz[:1])
            self.assertEqual(c[0]["status"], "ERROR")

    def test_unsat_wrong_colour_count(self):
        g = [[0, 0], [0, 0]]   # 1 colour on a 2x2: not a valid instance -> UNSAT
        for sv in ("match", "rr", "match_rr"):
            r = solver_native.run_batch(sv, "classify", 5, [("u", g)])[0]
            self.assertEqual((r["status"], r["count"]), ("UNSAT", 0))


class SatVariants(unittest.TestCase):
    def test_counts_and_stats(self):
        for p in _small(6):
            ref = (p.get("ref") or {}).get("count")
            for name in SAT_NEW:
                if name not in solvers.ADAPTERS:
                    continue
                r = solvers.ADAPTERS[name].solve(p["regions"], "classify", 20)
                with self.subTest(solver=name, id=p["id"]):
                    self.assertEqual(r["status"] in ("SOLVED", "UNSAT"), True)
                    if ref is not None:
                        self.assertEqual(r["count"], min(ref, 2))
                    for k in ("conflicts", "decisions", "propagations"):
                        self.assertIn(k, r)
                        self.assertIsNotNone(r[k])


if __name__ == "__main__":
    unittest.main()
