import unittest

from cat_solver import InputValidationError, parse_puzzle, validate_solution


def one_region_per_row(size):
    return [[f"r{row}" for _ in range(size)] for row in range(size)]


def payload(size, regions=None, **extra):
    return {
        "schema_version": "1.0",
        "size": size,
        "regions": regions if regions is not None else one_region_per_row(size),
        **extra,
    }


class ModelTests(unittest.TestCase):
    def test_valid_minimum_and_metadata(self):
        puzzle = parse_puzzle({"schema_version": "1.0", "size": 1, "regions": [["A"]], "id": "x"})
        self.assertEqual(puzzle.size, 1)
        self.assertEqual(puzzle.metadata["id"], "x")

    def test_invalid_shapes_and_region_count(self):
        cases = [
            {"size": 2, "regions": [["A", "B"]]},
            payload(2, [["A", "A"], ["A", "A"]]),
            payload(2, [["A", "B"], ["A"]]),
            payload(2, [["A", 4], ["B", "A"]]),
            payload(2, [["A", " "], ["B", "A"]]),
            payload(2, [["A", None], ["B", "A"]]),
            payload(2, region_labels=[]),
            payload(True, [["A"]]),
            payload(26, []),
            payload(0, []),
        ]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(InputValidationError):
                parse_puzzle(case)

    def test_invalid_coordinates_and_duplicates(self):
        for pair in ([-1, 0], [0, 2], [0.5, 1], [True, 0], [0]):
            with self.subTest(pair=pair), self.assertRaises(InputValidationError):
                parse_puzzle(payload(2, fixed_cats=[pair]))
        with self.assertRaises(InputValidationError):
            parse_puzzle(payload(2, blocked_cells=[[0, 0], [0, 0]]))
        with self.assertRaises(InputValidationError):
            parse_puzzle(payload(2, annotations={"observed_cats": [[0, 0], [0, 0]]}))
        with self.assertRaises(InputValidationError):
            parse_puzzle(payload(2, annotations=[]))

    def test_validator_column_region_adjacency_and_far_diagonal(self):
        puzzle = parse_puzzle(payload(4))
        self.assertIn("R2", {item.rule_id for item in validate_solution(puzzle, [0, 0, 2, 3])})

        regions = [
            ["A", "B", "C", "D"],
            ["B", "C", "D", "A"],
            ["C", "D", "A", "B"],
            ["D", "A", "B", "C"],
        ]
        same_region = parse_puzzle(payload(4, regions))
        self.assertIn("R3", {item.rule_id for item in validate_solution(same_region, [0, 3, 1, 2])})
        isolated_regions = [
            ["r0", "r2", "r0", "r0", "r0"],
            ["r1"] * 5,
            ["r2"] * 5,
            ["r3"] * 5,
            ["r4"] * 5,
        ]
        isolated = parse_puzzle(payload(5, isolated_regions))
        isolated_violations = validate_solution(isolated, [1, 3, 0, 4, 2])
        self.assertEqual([item.rule_id for item in isolated_violations], ["R3"])
        self.assertIn("R4", {item.rule_id for item in validate_solution(puzzle, [0, 1, 3, 2])})

        f4 = parse_puzzle(payload(5))
        self.assertEqual(validate_solution(f4, [1, 3, 0, 4, 2]), [])

    def test_validator_hard_constraints_and_bad_shape(self):
        puzzle = parse_puzzle(payload(4, fixed_cats=[[0, 1]], blocked_cells=[[2, 2]]))
        errors = validate_solution(puzzle, [1, 3, 0, 2])
        self.assertEqual(errors, [])
        self.assertTrue(validate_solution(puzzle, [0, 3, 0, 2]))
        self.assertTrue(validate_solution(puzzle, [1]))


if __name__ == "__main__":
    unittest.main()
