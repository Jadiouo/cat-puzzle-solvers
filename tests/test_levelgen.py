import itertools
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from levelgen import WEIGHTS, generate, grade, rescore, ugliness
from levelgen.board import MIN_REGION, count_solutions, is_connected, max_region_size, normalize
from levelgen.grade import (SolutionEliminated, State, lookahead, make_units, subset_elim,
                            t2, t3b)
from levelgen.pool import finalize, verify_unique

ROOT = Path(__file__).resolve().parents[1]


def g2(rows):
    return [[ord(ch) - 65 for ch in row] for row in rows]


def brute_solutions(grid):
    """Independent brute force over column permutations."""
    n = len(grid)
    out = []
    for p in itertools.permutations(range(n)):
        if any(abs(p[i] - p[i + 1]) <= 1 for i in range(n - 1)):
            continue
        if len({grid[i][p[i]] for i in range(n)}) == n:
            out.append(list(p))
    return out


# Small puzzles, frozen from the generator; each needs exactly this top technique.
EX = {
    "T3": (["BBBAA", "BBBAA", "DCCCA", "DEEAA", "DDEAA"], [4, 1, 3, 0, 2]),
    "T3b": (["BBBAA", "BBCAD", "BBCAD", "BBCED", "BEEED"], [3, 0, 2, 4, 1]),
    "T4": (["BAAAA", "BBDAA", "BDDAC", "EEDDC", "ECCCC"], [3, 1, 4, 2, 0]),
    "T5a": (["AAABB", "CCCCB", "CDDDB", "EDDDB", "EEDDD"], [2, 4, 0, 3, 1]),
    "T5b": (["CCCBBA", "CBBBAA", "CEBDDD", "CEDDFF", "CEFDFF", "CFFFFF"], [5, 2, 0, 3, 1, 4]),
}


def check_shape(tc, p):
    n = p["size"]
    reg, _ = normalize(p["regions"])
    tc.assertEqual(len(set(reg)), n)
    hi = max_region_size(n)
    for g in range(n):
        z = reg.count(g)
        tc.assertTrue(MIN_REGION <= z <= hi, (g, z))
        tc.assertTrue(is_connected(reg, n, g))
    sol = p["solution"]
    tc.assertEqual(sorted(sol), list(range(n)))
    tc.assertEqual(len({p["regions"][r][c] for r, c in enumerate(sol)}), n)
    tc.assertTrue(all(abs(sol[i] - sol[i + 1]) > 1 for i in range(n - 1)))


class TechniqueUnitTests(unittest.TestCase):
    def quad_state(self):
        reg = [0, 0, 1, 1, 0, 0, 1, 1, 2, 2, 3, 3, 2, 2, 3, 3]
        return State(4, make_units(reg, 4))

    def test_t2_single_candidate(self):
        s = self.quad_state()
        s.cand = {2} | set(range(4, 16))
        self.assertEqual(t2(s), 2)

    def test_t3_region_confined_to_row(self):
        s = self.quad_state()
        s.cand -= {4, 5}             # region A left with (0,0),(0,1): one row
        self.assertTrue(subset_elim(s, 1, 1))
        self.assertFalse({2, 3} & s.cand)
        self.assertTrue({0, 1} <= s.cand)

    def test_t3b_cover_elimination(self):
        s = self.quad_state()
        s.cand -= {9, 13}            # column 1 left with (0,1),(1,1), both covered by cell 0
        self.assertTrue(t3b(s))
        self.assertNotIn(0, s.cand)

    def test_t4_two_regions_two_rows(self):
        reg = [c for _ in range(4) for c in range(4)]    # vertical stripes
        s = State(4, make_units(reg, 4))
        s.cand -= {8, 9, 10, 11, 12, 13, 14, 15} & {r * 4 + c for r in (2, 3) for c in (0, 1)}
        self.assertFalse(subset_elim(s, 1, 1))
        self.assertTrue(subset_elim(s, 2, 4))
        for x in s.cand:
            if x < 8:
                self.assertIn(x % 4, (0, 1))

    def test_lookahead_finds_contradiction_without_removing_answer(self):
        rows, sol = EX["T5a"]
        reg = normalize(g2(rows))[0]
        s = State(5, make_units(reg, 5))
        s.cand -= set()              # fresh state: nothing placed yet
        sol_cells = {r * 5 + c for r, c in enumerate(sol)}
        while True:
            x = t2(s)
            if x is None:
                break
            s.place(x)
        d = lookahead(s)
        if d is not None:
            self.assertTrue(sol_cells <= (s.cand | s.cats))


class GradeTests(unittest.TestCase):
    def test_each_level_example(self):
        for lvl, (rows, sol) in EX.items():
            grid = g2(rows)
            self.assertEqual(brute_solutions(grid), [sol], lvl)
            g = grade(grid, solution=sol)
            self.assertTrue(g["solved"], lvl)
            self.assertEqual(g["level"], lvl)
            self.assertEqual(g["solution"], sol)
            self.assertGreater(g["counts"][lvl], 0)
            self.assertEqual(g["steps"], sum(g["counts"].values()))
            if lvl == "T5b":
                self.assertGreater(g["T5b_depth"], 1)

    def test_score_uses_weight_table(self):
        g = grade(g2(EX["T5b"][0]))
        c = g["counts"]
        expect = (WEIGHTS["T2"] * c["T2"] + WEIGHTS["T3"] * c["T3"] + WEIGHTS["T3b"] * c["T3b"]
                  + WEIGHTS["T4"] * c["T4"] + WEIGHTS["T5a"] * c["T5a"]
                  + WEIGHTS["T5b"] * c["T5b"] + WEIGHTS["T5b_depth"] * g["T5b_depth"])
        self.assertEqual(g["score"], expect)
        w = dict(WEIGHTS, T2=10)
        self.assertEqual(grade(g2(EX["T5b"][0]), weights=w)["score"], g["score"] + 9 * c["T2"])
        item = {"counts": c, "T5b_depth": g["T5b_depth"]}
        self.assertEqual(rescore(item, w), g["score"] + 9 * c["T2"])

    def test_wrong_solution_is_detected(self):
        rows, sol = EX["T3"]
        wrong = [0, 2, 4, 1, 3]
        self.assertNotEqual(wrong, sol)
        with self.assertRaises(SolutionEliminated):
            grade(g2(rows), solution=wrong)

    def test_flat_and_label_inputs(self):
        rows, sol = EX["T3b"]
        a = grade(rows)                                   # list of strings
        b = grade([ord(c) - 65 for r in rows for c in r])  # flat ints
        self.assertEqual(a["counts"], b["counts"])


class UglinessTests(unittest.TestCase):
    def test_ragged_worse_than_blocky(self):
        blocky = g2(["AAABB", "AAABB", "CCCDD", "CCCDD", "EEEEE"])
        ragged = g2(["ABABA", "ABABA", "ABABA", "CDCDC", "EEEEE"])
        self.assertGreater(ugliness(ragged), ugliness(blocky))


class GenerateTests(unittest.TestCase):
    def test_same_seed_same_output(self):
        for n in (6, 7):
            self.assertEqual(generate(n, 3), generate(n, 3))
        self.assertEqual(generate(6, 5, "T5a"), generate(6, 5, "T5a"))
        self.assertNotEqual(generate(6, 1)["regions"], generate(6, 2)["regions"])

    def test_bad_target(self):
        with self.assertRaises(ValueError):
            generate(6, 1, "T9")

    def test_generated_valid_unique_and_sound(self):
        for n, seeds in ((6, range(6)), (7, range(5)), (8, range(2))):
            for s in seeds:
                p = generate(n, s)
                self.assertIsNotNone(p)
                check_shape(self, p)
                self.assertEqual(brute_solutions(p["regions"]), [p["solution"]])
                self.assertEqual(count_solutions(normalize(p["regions"])[0], n, 2), 1)
                verify_unique(p)                           # cat_solver cross-check
                g = grade(p["regions"], solution=p["solution"])   # no step removes the answer
                self.assertTrue(g["solved"])
                self.assertEqual(g["solution"], p["solution"])

    def test_target_mode(self):
        hits = 0
        for s in range(3):
            p = generate(6, s, "T5a")
            if p is None:
                continue
            hits += 1
            check_shape(self, p)
            self.assertEqual(brute_solutions(p["regions"]), [p["solution"]])
            g = grade(p["regions"], solution=p["solution"])
            self.assertIn(g["level"], ("T5a", "T5b"))
            verify_unique(p)
        self.assertGreaterEqual(hits, 1)

    def test_verify_unique_rejects_multi_solution(self):
        rows = ["AAAAA", "BBBBB", "CCCCC", "DDDDD", "EEEEE"]
        p = {"size": 5, "regions": g2(rows), "solution": [0, 2, 4, 1, 3]}
        with self.assertRaises(ValueError):
            verify_unique(p)


class CliTests(unittest.TestCase):
    def test_pool_cli_roundtrip(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "levelgen" / "pool") as d:
            out = Path(d) / "p.json"
            cmd = [sys.executable, "-B", "-m", "levelgen", "pool", "--sizes", "6", "--count", "2",
                   "--probe-count", "1", "--seed", "7", "--out", str(out)]
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            pool = json.loads(out.read_text())
            self.assertEqual(len(pool["puzzles"]), 3)
            keys = {"id", "size", "regions", "solution", "counts", "level", "score", "ugliness",
                    "region_min", "region_max", "seed"}
            for p in pool["puzzles"]:
                self.assertTrue(keys <= set(p))
                self.assertEqual(brute_solutions(p["regions"]), [p["solution"]])
            out2 = Path(d) / "q.json"
            subprocess.run(cmd[:-1] + [str(out2)], cwd=ROOT, capture_output=True, text=True)
            a = [(p["regions"], p["solution"], p["score"]) for p in pool["puzzles"]]
            b = [(p["regions"], p["solution"], p["score"]) for p in json.loads(out2.read_text())["puzzles"]]
            self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
