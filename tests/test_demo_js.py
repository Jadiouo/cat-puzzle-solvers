"""Checks the browser solver (docs/js/solver.js) against the C++ solver, puzzle by puzzle.

For S1 (all), S5 (all), S6m (all) and S3 with N<=20 (all) it runs the C++ binary in classify mode for
`bitmask` and `match`, then runs the same puzzles through tests/js/verify_solver.js. The solution-count
class and the node count must be equal for every puzzle and both algorithms.
Skipped when node, the C++ binary (and a compiler to build it) are missing.
Run: python3 -m unittest tests.test_demo_js -v   (or  python3 tests/test_demo_js.py)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
EXE = os.path.join(ROOT, "native", "build", "cat_native")
SUITES = os.path.join(ROOT, "bench", "suites")
CPP_TIMEOUT_S = 20      # C++ per-puzzle timeout; puzzles that exceed it are skipped (and reported)


def load(suite, maxn=None):
    with open(os.path.join(SUITES, suite + ".json")) as fh:
        d = json.load(fh)
    out = []
    for p in d["puzzles"]:
        if maxn is None or p["n"] <= maxn:
            out.append({"suite": suite, "id": p["id"], "n": p["n"], "regions": p["regions"]})
    return out


def run_cpp(solver, puzzles):
    inp = "".join(f"{p['id']} {p['n']} " + " ".join(str(v) for row in p["regions"] for v in row) + "\n" for p in puzzles)
    r = subprocess.run([EXE, "-s", solver, "-m", "classify", "-t", str(CPP_TIMEOUT_S)],
                       input=inp, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-300:])
    res = {}
    for line in r.stdout.splitlines():
        j = json.loads(line)
        res[j["id"]] = {"status": j["status"], "count": j["count"], "nodes": j["nodes"]}
    return res


class DemoJsMatchesCpp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("node not installed")
        if not os.path.isfile(EXE):
            if shutil.which("make") and shutil.which("g++"):
                subprocess.run(["make", "-C", os.path.join(ROOT, "native"), "-j4"], capture_output=True)
            if not os.path.isfile(EXE):
                raise unittest.SkipTest("native/build/cat_native missing and could not be built")

    def test_node_counts_and_classes_identical(self):
        puzzles = load("S1") + load("S5") + load("S6m") + load("S3", maxn=20)
        self.assertGreater(len(puzzles), 400)
        exp = {a: run_cpp(a, puzzles) for a in ("bitmask", "match")}
        for p in puzzles:
            p["exp"] = {a: exp[a][p["id"]] for a in exp}
        with tempfile.TemporaryDirectory() as td:
            f = os.path.join(td, "cases.json")
            with open(f, "w") as fh:
                json.dump(puzzles, fh)
            r = subprocess.run(["node", os.path.join(ROOT, "tests", "js", "verify_solver.js"), f],
                               capture_output=True, text=True)
        print("\n" + r.stdout)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-500:])
        self.assertIn("mismatches=0", r.stdout)


if __name__ == "__main__":
    unittest.main()
