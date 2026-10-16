import json
import unittest
from pathlib import Path

from cat_solver import InputValidationError, SolveOptions, parse_puzzle, solve, validate_solution

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def row_regions(size):
    return [[f"R{row}" for _ in range(size)] for row in range(size)]


def board(size, **extra):
    return parse_puzzle({
        "schema_version": "1.0",
        "size": size,
        "regions": row_regions(size),
        **extra,
    })


class SolverTests(unittest.TestCase):
    def test_f1_and_unsat_fixed_cell(self):
        result = solve(parse_puzzle({"schema_version": "1.0", "size": 1, "regions": [["A"]]}))
        self.assertEqual((result.status, result.uniqueness, result.solutions), ("SOLVED", "UNIQUE", [[0]]))
        blocked = parse_puzzle({
            "schema_version": "1.0", "size": 1, "regions": [["A"]], "blocked_cells": [[0, 0]]
        })
        self.assertEqual(solve(blocked).status, "UNSAT")

    def test_f2_classify_first_all_and_variants(self):
        puzzle = board(4)
        all_result = solve(puzzle, SolveOptions(mode="all", timeout_ms=None))
        self.assertEqual(all_result.solutions, [[1, 3, 0, 2], [2, 0, 3, 1]])
        self.assertEqual((all_result.uniqueness, all_result.search_complete), ("MULTIPLE", True))
        classify = solve(puzzle)
        self.assertEqual((classify.uniqueness, len(classify.solutions)), ("MULTIPLE", 2))
        first = solve(puzzle, SolveOptions(mode="first"))
        self.assertEqual((first.uniqueness, len(first.solutions)), ("UNKNOWN", 1))
        self.assertFalse(first.search_complete)

        unique = solve(board(4, blocked_cells=[[0, 2]]))
        self.assertEqual((unique.uniqueness, unique.solutions), ("UNIQUE", [[1, 3, 0, 2]]))
        unsat = solve(board(4, blocked_cells=[[0, 1], [0, 2]]))
        self.assertEqual((unsat.status, unsat.search_complete), ("UNSAT", True))
        fixed = solve(board(4, fixed_cats=[[0, 1]]))
        self.assertEqual(fixed.solutions, [[1, 3, 0, 2]])

    def test_small_and_five_by_five_counts(self):
        for size in (2, 3):
            result = solve(board(size), SolveOptions(mode="all", timeout_ms=None))
            self.assertEqual((result.status, result.solutions), ("UNSAT", []))
        result = solve(board(5), SolveOptions(mode="all", timeout_ms=None))
        self.assertEqual(len(result.solutions), 14)
        self.assertEqual(len({tuple(item) for item in result.solutions}), 14)
        self.assertTrue(all(not validate_solution(board(5), item) for item in result.solutions))

    def test_fixed_conflicts_are_unsat(self):
        cases = [
            board(4, fixed_cats=[[0, 0], [0, 1]]),
            board(4, fixed_cats=[[0, 0]], blocked_cells=[[0, 0]]),
            board(4, fixed_cats=[[0, 0], [1, 1]]),
            board(4, fixed_cats=[[0, 0], [2, 2]]),
        ]
        for puzzle in cases:
            self.assertEqual(solve(puzzle).status, "UNSAT")

    def test_fixed_lower_neighbor_is_checked_during_mrv_search(self):
        result = solve(board(4, fixed_cats=[[2, 0]]))
        self.assertEqual((result.uniqueness, result.solutions), ("UNIQUE", [[1, 3, 0, 2]]))

    def test_disconnected_region_ids_are_shared(self):
        regions = [
            ["A", "B", "C", "D"],
            ["B", "C", "D", "A"],
            ["C", "A", "B", "D"],
            ["D", "B", "C", "A"],
        ]
        puzzle = parse_puzzle({"schema_version": "1.0", "size": 4, "regions": regions})
        self.assertIn("R3", {v.rule_id for v in validate_solution(puzzle, [0, 1, 2, 3])})

    def test_invalid_options_are_results(self):
        puzzle = board(4)
        for options in (
            SolveOptions(mode="bad"),
            SolveOptions(timeout_ms=0),
            SolveOptions(timeout_ms=True),
            SolveOptions(max_nodes=-1),
            SolveOptions(max_nodes=True),
            SolveOptions(mark_policy="bad"),
        ):
            self.assertEqual(solve(puzzle, options).status, "INVALID_INPUT")

    # the former private fixture was replaced; the fixture is the self-generated
    # tests/fixtures/sample10.json (levelgen seed 1). Changed vs. the old test:
    # fixture path, name, and the expected unique solution. Properties kept:
    # base/trust-cats -> UNIQUE with the same solution; trust-all -> UNSAT
    # (the fixture has one deliberately wrong cross on a solution cat).
    def test_sample10_three_policies(self):
        puzzle = parse_puzzle(json.loads((FIXTURES / "sample10.json").read_text(encoding="utf-8")))
        expected = [6, 1, 5, 0, 3, 7, 2, 8, 4, 9]
        for policy in ("base", "trust-cats"):
            result = solve(puzzle, SolveOptions(mark_policy=policy, timeout_ms=None))
            self.assertEqual((result.uniqueness, result.solutions), ("UNIQUE", [expected]))
        trust_all = solve(puzzle, SolveOptions(mark_policy="trust-all", timeout_ms=None))
        self.assertEqual((trust_all.status, trust_all.solutions), ("UNSAT", []))

    def test_added_hard_limits_cannot_add_solutions(self):
        puzzle = board(5)
        baseline = solve(puzzle, SolveOptions(mode="all", timeout_ms=None))
        restricted = solve(
            board(5, fixed_cats=[[0, baseline.solutions[0][0]]]),
            SolveOptions(mode="all", timeout_ms=None),
        )
        self.assertLessEqual(set(map(tuple, restricted.solutions)), set(map(tuple, baseline.solutions)))

    def test_region_renaming_preserves_solution_set(self):
        original = board(5)
        renamed = parse_puzzle({
            "schema_version": "1.0",
            "size": 5,
            "regions": [[f"renamed-{row}" for _ in range(5)] for row in range(5)],
        })
        left = solve(original, SolveOptions(mode="all", timeout_ms=None))
        right = solve(renamed, SolveOptions(mode="all", timeout_ms=None))
        self.assertEqual(set(map(tuple, left.solutions)), set(map(tuple, right.solutions)))

    # Renamed from the level-46 transcription regression; same checks (size 10,
    # 10 distinct regions, the known wrong cross present) on the new fixture,
    # where the wrong cross is [1, 1] instead of [1, 7].
    def test_sample10_fixture_regression_exactly(self):
        puzzle = json.loads((FIXTURES / "sample10.json").read_text(encoding="utf-8"))
        self.assertEqual(puzzle["size"], 10)
        self.assertEqual(len({region for row in puzzle["regions"] for region in row}), 10)
        self.assertIn([1, 1], puzzle["annotations"]["observed_crosses"])


if __name__ == "__main__":
    unittest.main()
