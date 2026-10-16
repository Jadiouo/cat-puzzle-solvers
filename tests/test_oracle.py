import itertools
import random
import unittest

from cat_solver import SolveOptions, parse_puzzle, solve


def oracle(regions, fixed=(), blocked=()):
    size = len(regions)
    results = set()
    fixed_by_row = {row: column for row, column in fixed}
    for columns in itertools.permutations(range(size)):
        if any(columns[row] != column for row, column in fixed_by_row.items()):
            continue
        cats = {(row, columns[row]) for row in range(size)}
        if cats & set(blocked):
            continue
        if len({regions[row][columns[row]] for row in range(size)}) != size:
            continue
        if any(abs(columns[row + 1] - columns[row]) <= 1 for row in range(size - 1)):
            continue
        results.add(columns)
    return results


class OracleTests(unittest.TestCase):
    def test_seeded_random_boards_match_independent_permutation_oracle(self):
        case_index = 0
        for seed in (20261012, 17, 46):
            rng = random.Random(seed)
            for _ in range(30):
                size = rng.randint(1, 7)
                labels = [f"c{index}" for index in range(size)]
                regions = [[rng.choice(labels) for _ in range(size)] for _ in range(size)]
                for row, label in enumerate(labels):
                    regions[row][row] = label
                blocked_set = set()
                fixed = []
                for _ in range(rng.randrange(3)):
                    blocked_set.add((rng.randrange(size), rng.randrange(size)))
                if rng.random() < 0.35:
                    fixed = [[rng.randrange(size), rng.randrange(size)]]
                payload = {
                    "schema_version": "1.0",
                    "size": size,
                    "regions": regions,
                    "fixed_cats": fixed,
                    "blocked_cells": [list(cell) for cell in sorted(blocked_set)],
                }
                puzzle = parse_puzzle(payload)
                expected = oracle(
                    regions, [tuple(cell) for cell in fixed], [tuple(cell) for cell in blocked_set]
                )
                result = solve(puzzle, SolveOptions(mode="all", timeout_ms=None))
                self.assertEqual(result.status, "UNSAT" if not expected else "SOLVED", case_index)
                self.assertEqual(set(map(tuple, result.solutions)), expected, case_index)
                self.assertTrue(result.search_complete, case_index)
                case_index += 1


if __name__ == "__main__":
    unittest.main()
