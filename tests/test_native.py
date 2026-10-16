"""Fidelity of the C++ ports (native/cat_native): same count and same node count as the Python solvers.
Skipped when native/build/cat_native has not been built (make -C native)."""
import json
import os
import unittest

from bench import solvers  # noqa: F401  (import first: avoids a circular import)
from bench import solver_bitmask, solver_dlx, solver_hybrid, solver_native

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = {"bitmask": solver_bitmask.BitmaskAdapter, "hybrid": solver_hybrid.HybridAdapter,
      "dlx": solver_dlx.DLXAdapter}


def _puzzles(suite, k):
    with open(os.path.join(ROOT, "bench", "suites", suite + ".json")) as f:
        ps = json.load(f)["puzzles"]
    ps = [p for p in ps if p["n"] <= 10]
    step = max(1, len(ps) // k)
    return ps[::step][:k]


@unittest.skipUnless(solver_native.available(), "native/build/cat_native not built (make -C native)")
class NativeFidelity(unittest.TestCase):
    def test_same_count_and_nodes(self):
        pz = _puzzles("S1", 8) + _puzzles("S2", 3)
        for sv, cls in PY.items():
            for mode in ("first", "classify", "count"):
                nat = solver_native.run_batch(sv, mode, 20, [(p["id"], p["regions"]) for p in pz])
                for p, c in zip(pz, nat):
                    r = cls().solve(p["regions"], mode, 20)
                    with self.subTest(solver=sv, mode=mode, id=p["id"]):
                        self.assertEqual(r["status"], c["status"])
                        self.assertEqual(r["count"], c["count"])
                        self.assertEqual(r["nodes"], c["nodes"])
                        if mode != "count":
                            self.assertEqual(r["solutions"], c["solutions"])

    def test_adapter_and_unsat(self):
        a = solver_native.NATIVE_ADAPTERS["native_hybrid"]
        p = _puzzles("S1", 1)[0]
        res = a.solve(p["regions"], "classify", 5)
        self.assertEqual((res["status"], res["count"], res["complete"]), ("SOLVED", 1, True))
        # fewer colours than N -> no solution
        bad = [[0] * 5 for _ in range(5)]
        for sv in ("native_bitmask", "native_hybrid"):
            self.assertEqual(solver_native.NATIVE_ADAPTERS[sv].solve(bad, "count", 5)["count"], 0)

    def test_timeout_is_reported(self):
        pz = [p for p in json.load(open(os.path.join(ROOT, "bench", "suites", "S4.json")))["puzzles"] if p["n"] >= 18][:1]
        r = solver_native.run_batch("bitmask", "count", 0.05, [(pz[0]["id"], pz[0]["regions"])])[0]
        self.assertEqual((r["status"], r["count"], r["complete"]), ("TIMEOUT", None, False))
        self.assertLess(r["elapsed"], 1.0)


if __name__ == "__main__":
    unittest.main()
